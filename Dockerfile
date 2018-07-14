FROM python:3-alpine
WORKDIR /app

# for reflex - compiling needed for crypto
RUN apk add --no-cache gcc libc-dev libffi-dev \
      linux-headers make python3-dev openssl-dev && \
    pip3 --no-cache-dir install rfxcmd
    #apk del .build-deps && rm -rf ~/.cache

# the app
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt
COPY jira_time.py jira-report-time jira-slack-time /app/

## reflex
CMD /usr/local/bin/launch app
