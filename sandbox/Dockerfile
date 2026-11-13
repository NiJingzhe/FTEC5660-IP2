FROM python:3.12-slim
ARG CAD_PACKAGE=cadquery==2.8.0
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "${CAD_PACKAGE}" pillow
WORKDIR /work
ENV MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
