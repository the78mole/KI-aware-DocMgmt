# marker-pdf als HTTP-Dienst (marker_server), nur CPU.
# Die Modelle werden beim ersten Start geladen und im Volume unter /models zwischengespeichert.
FROM python:3.12-slim

ARG MARKER_VERSION=2.0.0
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir "marker-pdf==${MARKER_VERSION}" fastapi uvicorn python-multipart

RUN useradd --system --uid 10001 --create-home marker && mkdir -p /models /work && chown marker /models /work
USER marker
WORKDIR /work
ENV TORCH_DEVICE=cpu HF_HOME=/models MODEL_CACHE_DIR=/models
EXPOSE 8001
CMD ["marker_server", "--host", "0.0.0.0", "--port", "8001"]
