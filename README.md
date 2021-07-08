# asyncio Web checker

concept demo: "Monitor website availability over the network using kafka"

## Functional requirements

- Periodically collect metrics on specified websites:
  - HTTP status code
  - response time
  - optionally check response against regex
  - send via Kafka to consumer process

## Usage

This has only been tested with Python 3.9 - it may work with earlier versions. If you are going to use `keyring` then `keyring set postgresql <username>` and follow the prompts.

Setup from code

- you will need to hack on the configuration especially service hostnames and details
- `python -m pip install poetry`
- `cd webcheck` or where you cloned to. Most commands here assume you are in dir with `__main__.py`
- `poetry install` install dependencies. Note there is a `setup.py` also packaged which itself is built with `poetry build`
- if you are using certs to connect to Kafka, copy `ca.pem` `service.cert` `service.key` into the `webcheck` directory.
- `python . --help` displays the CLI commands, most of which have their own help. Examples:
  - `python . url-check --url https://example.org`  # run webcheck logic on url
  - `python . pg-table-drop <password>`  # doesn't read from keyring to reduce accidental deletion - you can safely run it and abort before damage is done.

### Run tests

- `pytest` - there are almost no tests.

Inspect the defaults in `webcheck.yaml` and adjust as necessary.

### Try minimal end to end webchecker

- `python . pg-table-create`  # create postgres tables if not already present.
- `python . round-trip --interval 15`  # run a self-contained end to end check -> kafka -> postgres.
- to terminate, ctrl-c twice.

### Scale it up

Running individual producer and consumer processes allows this to scale - noting that I have only a couple or URL entries in the config.

- Increase the kafka topic `partitions` for the desired consumer concurrency/hot-spare.

Start up the consumer and producer

- `python . consumer`
- `python . producer`

Try adding a 2nd consumer

- `python . consumer`

More producers can be added also however you would want to provide them with different URLs.
