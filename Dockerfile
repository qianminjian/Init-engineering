FROM python:3.12-slim

LABEL org.opencontainers.image.title="ae — Init Engineering"
LABEL org.opencontainers.image.description="Claude Code Agent Skill: project environment initialization"
LABEL org.opencontainers.image.source="https://github.com/qianminjian/Init-engineering"

WORKDIR /app

COPY pyproject.toml .
COPY README.md .
COPY auto_engineering/ auto_engineering/

RUN pip install --no-cache-dir .

ENTRYPOINT ["ae"]
CMD ["--help"]
