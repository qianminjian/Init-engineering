FROM python:3.12-slim

LABEL org.opencontainers.image.title="ae — Init Engineering"
LABEL org.opencontainers.image.description="Claude Code Agent Skill: project environment initialization"
LABEL org.opencontainers.image.source="https://github.com/qianminjian/Init-engineering"

WORKDIR /app

# DI-P1-4: 复制 README/CHANGELOG/LICENSE — hatch wheel 打包会引用这些文件
# (见 [tool.hatch.build.targets.wheel.force-include]),缺一则 uv/pip build 失败
COPY pyproject.toml .
COPY README.md .
COPY CHANGELOG.md .
COPY LICENSE .
COPY SKILL.md .
COPY auto_engineering/ auto_engineering/

RUN pip install --no-cache-dir .

ENTRYPOINT ["ae"]
CMD ["--help"]
