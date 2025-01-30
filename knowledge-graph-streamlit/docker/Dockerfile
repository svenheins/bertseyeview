FROM python:3.7-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

#RUN git clone https://github.com/streamlit/streamlit-example.git .

COPY requirements.txt .

RUN pip3 install -r requirements.txt

EXPOSE 8501

# streamlit-specific commands
RUN mkdir -p /root/.streamlit
RUN bash -c 'echo -e "\
    [general]\n\
    email = \"\"\n\
    " > /root/.streamlit/credentials.toml'
RUN bash -c 'echo -e "\
    [server]\n\
    enableCORS = false\n\
    " > /root/.streamlit/config.toml'

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "1_Search.py", "--server.port=8501", "--server.headless=true", "--global.developmentMode=false", "--server.address=0.0.0.0"]
