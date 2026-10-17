ARG BASE_IMAGE=registry.linuxone.cloud.marist.edu/l1cc/jupyterlab-image-s390x:latest
FROM ${BASE_IMAGE}
WORKDIR /opt/allpower
COPY . /opt/allpower
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/allpower ALLPOWER_DB=/opt/allpower/data/allpower.sqlite3
EXPOSE 8080
CMD ["python3","-m","allpower.server","--host","0.0.0.0"]
