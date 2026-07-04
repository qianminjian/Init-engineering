"""InitWorker — 5 阶段流水线编排器（参考 Copier Worker）。

v2.5 拆分（501→≤300 行）：阶段方法全部抽到 scaffold_phase_funcs.py，
本模块只保留 InitWorker dataclass + execute() 编排器。

设计：
- InitWorker 仅作"配置容器 + 编排器"（保持单一职责）
- 5 阶段为模块级函数：phase_detect/phase_prompt/phase_render/phase_tasks/phase_finalize
- 锁/前置条件/钩子等横切关注点继续下沉到 scaffold_lock/scaffold_prereq
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .answers import AnswersMap
from .config import TemplateConfig
from .errors import InitInterruptedError
from .scaffold_lock import InitLock
from .scaffold_phase_funcs import (
    phase_detect,
    phase_finalize,
    phase_prompt,
    phase_render,
)
from .scaffold_prereq import check_template_version
from .scaffold_render import render_to as _render_to
from .scaffold_tasks_runner import TaskRunner, run_builtin_hooks, run_tasks_phase

# Backward-compat re-export: 测试 patch("init_engineering.init.scaffold_phases.<name>")
# 必须仍能找到该符号 — 实际实现迁移，但语义未变。
TaskRunner = TaskRunner
run_builtin_hooks = run_builtin_hooks
# 同理：测试 patch("init_engineering.init.scaffold_phases._render_to")
_render_to = _render_to

_logger = logging.getLogger(__name__)


@dataclass
class InitResult:
    dst_path: Path
    files: list[Path] = field(default_factory=list)
    answers: dict = field(default_factory=dict)
    project_type: str = ""


@dataclass
class InitWorker:
    dst_path: Path
    project_type: str | None = None
    language: str | None = None
    package_manager: str | None = None
    ci_platform: str | None = None
    test_runner: str | None = None
    use_typescript: bool | None = None
    use_lefthook: bool | None = None
    use_docker: bool | None = None
    force: bool = False
    defaults: bool = False
    overwrite: bool = False
    quiet: bool = False
    verbose: bool = False
    pretend: bool = False
    skip_tasks: bool = False
    cleanup_on_error: bool = True
    incremental: bool = False
    strict: bool = False
    # PE-P0-1: --no-install CLI flag — 跳过 package_manager install 阶段
    no_install: bool = False
    templates_suffix: str | None = None
    preserve_symlinks: bool | None = None
    template_dir_override: Path | None = None
    # PE-P1-4: 全局钩子超时(秒),None 走 TaskRunner 默认 (300s)
    hook_timeout: int | None = None

    _current_phase: str = field(init=False, default="")
    _template: TemplateConfig = field(init=False, default=None)
    _answers: AnswersMap = field(init=False, default_factory=AnswersMap)
    _cleanup_hooks: list[Callable] = field(default_factory=list, init=False)
    _previous_answers: AnswersMap | None = field(init=False, default=None)
    _created_files: set[str] = field(default_factory=set, init=False)
    _mode: str = field(init=False, default="fresh")
    _lock: InitLock | None = field(init=False, default=None)
    _detection: object = field(init=False, default=None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        return False

    def _cleanup(self) -> None:
        # P2-4: cleanup logging 改用模块 logger (logging.warning 是 root logger,
        # 无 handler 时默认吞掉, 调试时看不到错误)
        for hook in self._cleanup_hooks:
            try:
                hook()
            except Exception as e:
                _logger.warning("cleanup hook failed: %s", e)
        if self._lock is not None:
            self._lock.release()
            self._lock = None

    def execute(self) -> InitResult:
        if self.verbose:
            _logger.debug("InitWorker starting: dst=%s type=%s", self.dst_path, self.project_type)
        if self.pretend and not self.quiet:
            # PE-AUDIT-P0-2: 业务消息改用 logger,让 --verbose 真正生效
            _logger.info("[DRY RUN] 模拟执行，不产生文件")

        dst_existed_before = self.dst_path.exists()

        # Phase 1 — detect
        self._current_phase = "detect"
        _logger.debug("Phase: detect")
        self._phase_detect()

        # Phase 2 — prompt
        self._current_phase = "prompt"
        _logger.debug("Phase: prompt")
        self._phase_prompt()

        if self.pretend:
            return InitResult(
                dst_path=self.dst_path,
                project_type=self.project_type or "",
            )

        tmpdir = Path(tempfile.mkdtemp(prefix="ae-init-"))
        self._cleanup_hooks.append(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        generated: list[Path] = []

        try:
            # Phase 3 — render
            self._current_phase = "render"
            _logger.debug("Phase: render")
            if self._template.message_before and not self.quiet:
                # PE-AUDIT-P0-2: 模板 message_before 走 logger
                _logger.info("%s", self._template.message_before)
            generated = self._phase_render(tmpdir)

            # Phase 4 — tasks
            self._current_phase = "tasks"
            _logger.debug("Phase: tasks")
            if not self.skip_tasks:
                self._phase_tasks(tmpdir)
                if self._template.message_after and not self.quiet:
                    # PE-AUDIT-P0-2: 模板 message_after 走 logger
                    _logger.info("%s", self._template.message_after)

            # Phase 5 — finalize
            self._current_phase = "finalize"
            did_create_dst = self._phase_finalize(tmpdir, generated)

        except InitInterruptedError:
            partial_path = self._answers.save_partial()
            if not self.quiet:
                # PE-AUDIT-P0-2: 中断消息走 logger (INFO 级别让默认输出可见)
                _logger.info("\n已中断。部分答案已保存到: %s", partial_path)
                _logger.info("恢复: ae init --from-answers %s", partial_path)
            raise

        except Exception:
            if self.cleanup_on_error and not dst_existed_before and self.dst_path.exists():
                shutil.rmtree(self.dst_path)
            raise

        return InitResult(
            dst_path=self.dst_path,
            files=generated,
            answers=self._answers.to_answers_file(),
            project_type=self.project_type or "",
        )

    # ─── 兼容层：原内部方法（v2.5 拆到 scaffold_prereq/scaffold_phase_funcs 后保留 thin wrapper）──

    def _check_template_version(self) -> None:
        """模板 _min_ae_version vs 已安装 __version__."""
        if self._template is None:
            return
        check_template_version(self._template.min_ae_version)

    def _check_prerequisites(self) -> None:
        """基础工具链 + 语言工具链检查."""
        from .scaffold_prereq import check_basic_tools, check_language_tools
        check_basic_tools()
        check_language_tools(self.language, self.skip_tasks)

    # ─── 阶段方法（薄包装，monkey-patch 友好）────────────────────────
    # 历史：原 InitWorker 拥有 _phase_* 方法。v2.5 拆到 scaffold_phase_funcs.py
    # 后保留为 thin wrapper — 一行委托，让 monkeypatch.setattr(worker, ...)
    # 仍能替换阶段逻辑（向后兼容测试）。

    def _phase_detect(self) -> None:
        # B1: 必须捕获 lock 对象 — 否则 fd 立刻被 GC,锁瞬间释放,失去并发保护。
        self.project_type, self._mode, self._detection, self._lock = phase_detect(
            project_type=self.project_type,
            dst_path=self.dst_path,
            language=self.language,
            skip_tasks=self.skip_tasks,
            incremental=self.incremental,
            force=self.force,
            pretend=self.pretend,
            defaults=self.defaults,
        )

    def _phase_prompt(self) -> None:
        detection_for_prompt = (
            self._detection if hasattr(self._detection, "language") else None
        )
        self._template, self._answers = phase_prompt(
            project_type=self.project_type,
            defaults=self.defaults,
            previous_answers=self._previous_answers,
            language=self.language,
            package_manager=self.package_manager,
            ci_platform=self.ci_platform,
            test_runner=self.test_runner,
            use_typescript=self.use_typescript,
            use_lefthook=self.use_lefthook,
            use_docker=self.use_docker,
            detection=detection_for_prompt,
        )
        check_template_version(self._template.min_ae_version)

    def _phase_render(self, tmpdir: Path) -> list[Path]:
        return phase_render(
            answers=self._answers,
            template=self._template,
            dst_path=self.dst_path,
            tmpdir=tmpdir,
            overwrite=self.overwrite,
            templates_suffix=self.templates_suffix,
            preserve_symlinks=self.preserve_symlinks,
            template_dir_override=self.template_dir_override,
            strict=self.strict,
        )

    def _phase_tasks(self, tmpdir: Path) -> None:
        run_tasks_phase(
            tmpdir=tmpdir,
            dst_path=self.dst_path,
            template=self._template,
            answers=self._answers,
            current_phase=self._current_phase,
            strict=self.strict,
            quiet=self.quiet,
            # PE-P1-4: hook_timeout 透传到 TaskRunner
            default_timeout=self.hook_timeout,
            # PE-P0-1: no_install 跳过 pm install
            no_install=self.no_install,
        )

    def _phase_finalize(self, tmpdir: Path, generated: list[Path]) -> bool:
        did_create = phase_finalize(
            answers=self._answers,
            project_type=self.project_type,
            template=self._template,
            tmpdir=tmpdir,
            dst_path=self.dst_path,
            created_files=self._created_files,
            mode=self._mode,
            quiet=self.quiet,
            # P2-2: 传 generated 给 phase_finalize 打印真实文件数 (之前写死 0)
            generated=generated,
        )
        # PE-P0-4: 在 dst_path (而非 tmpdir) 重新跑依赖安装,修复 .venv shebang 断裂
        from .phases.finalize import phase_post_install
        phase_post_install(
            answers=self._answers,
            dst_path=self.dst_path,
            strict=self.strict,
            quiet=self.quiet,
            no_install=self.no_install,
            # PE-AUDIT-P0-1: 透传 hook_timeout
            timeout=self.hook_timeout,
        )
        return did_create
