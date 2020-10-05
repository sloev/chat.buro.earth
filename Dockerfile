FROM python:latest


RUN apt-get install imagemagick && \
    pip install poetry

ADD pyproject.toml .
ADD poetry.lock poetry.lock

RUN poetry install

RUN convert -list font

ADD chatburo/ chatburo/

EXPOSE 8000
CMD ["poetry", "run", "start"]
