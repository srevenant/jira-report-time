FROM python:3-alpine
WORKDIR /app

# for reflex - compiling needed for crypto
RUN apk add --no-cache --virtual .build-deps \
        gcc libc-dev libffi-dev \
        linux-headers make python3-dev && \
    apk add --no-cache libffi openssl && \
    pip3 --no-cache-dir install rfxcmd && \
    apk del .build-deps && rm -rf ~/.cache

# the app
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt
COPY jira-report-time config.json.in /app/

## reflex
CMD /usr/local/bin/launch app
