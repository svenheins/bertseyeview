FROM python:3.7

COPY requirements.txt requirements.txt
RUN python -m pip install --upgrade pip
RUN pip3 install -r requirements.txt

ADD "__main__.py" /

ENTRYPOINT [ "python", "./__main__.py" ]
