FROM python:3.7-slim
WORKDIR /code
#RUN apk add --no-cache gcc musl-dev linux-headers
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
ENV FLASK_APP=neo4j_api.py
ENV FLASK_RUN_HOST=0.0.0.0
EXPOSE 5000
COPY . .
CMD ["flask", "run"]