FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY stance ./stance
COPY apps ./apps
COPY eval ./eval

# CPU-only torch first — the default PyPI wheel pulls in several GB of
# unused NVIDIA CUDA packages; Cloud Run containers have no GPU.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -e ".[retrieval,agents,ui]"

# After the install, not before: a runtime-only config file, changing it
# must never invalidate the expensive torch/extras layer above.
COPY .streamlit ./.streamlit

EXPOSE 8080

CMD ["streamlit", "run", "apps/ui/app.py", \
     "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
