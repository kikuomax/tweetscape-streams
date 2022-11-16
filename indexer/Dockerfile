FROM alpine:3.16

RUN apk add --no-cache postgresql14 python3 py3-pip

RUN mkdir /var/run/indexer
WORKDIR /var/run/indexer

COPY cdk/lambda/indexer-dependencies ./indexer-dependencies/
RUN python3 -m pip install -r indexer-dependencies/requirements.txt python-dotenv psycopg2-binary

COPY cdk/lambda/index-all-streams ./index-all-streams/

CMD [ "python3" ]
