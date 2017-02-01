FROM canopytax/alpine

RUN apk add --update python3 &&\
    python3 -m ensurepip &&\
    rm /var/cache/apk/*

COPY requirements.txt  /tmp/
RUN python3 -m pip install -r /tmp/requirements.txt
    
COPY scripts /scripts

