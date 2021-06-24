# Web checker

concept demo: "Monitor website availability over the network"

Being a homework problem some @todos will be found.

## Functions

- Periodically collect metrics on specified websites:
  - HTTP status code
  - response time
  - optionally check response against regex

## Non functional requirements

- use cloud Kafka for sending results
- use cloud postgresql for persisting results
- could handle a "reasonable amount of checks over a longer period of time"
- includes tests
- properly packaged

## Usage

This has only been tested with Python 3.9 - it may work with earlier versions. If you are going to use `keyring` then `keyring set postgresql avnadmin` and follow the prompts.

Setup from code

- `git clone [github repo](https://github.com/aiven-recruitment/seniorsre-20210618-paulsorenson)` or download tarball.
- `python -m pip install poetry`
- `cd webcheck` # most commands here assume you are in dir with `__main__.py`
- `poetry install` # install dependencies. Note there is a `setup.py` also packaged which itself is built with `poetry build`
- copy `ca.pem` `service.cert` `service.key` kafka ssl files into webcheck directory. These are available for download on the [aiven kafka console](https://console.aiven.io/project/metrak-749b/services/kafka-1c4efd3)
- `python . --help` # displays the CLI commands, most of which have their own help. Examples:
  - `python . url-check --url https://aiven.io`  # run webcheck logic on url
  - `python . pg-table-drop <password>`  # doesn't read from keyring to reduce accidental deletion - you can safely run it and abort before damage is done.

Run tests

- `pytest`

Inspect the defaults in `webcheck.yaml` and adjust as necessary.

Try minimal end to end webchecker

- `python . pg-table-create`  # create postgres tables if not already present.
- `python . round-trip --interval 15`  # run a self-contained end to end check -> kafka -> postgres.
- to terminate, ctrl-c twice.

Scale it up

Running individual producer and consumer processes allows this to scale - noting that I have only a couple or URL entries in the config.

- Use `aiven.io` service dashboard to increase the `partitions` for the desired consumer concurrency/hot-spare.

Start up the consumer and producer

- `python . consumer`
- `python . producer --interval 15`

Try adding a 2nd consumer

- `python . consumer`

More producers can be added also however you would want to provide them with different URLs.


## Dev tools

- language: Python 3.9
- dependencies: see `pyproject.toml`
- editor: vscode
- OS: linux (fedora 34)
- pre-commit checks: [pre-commit](https://pre-commit.com/)
- repo: [github](github.com)
- packaging: [poetry](https://python-poetry.org/)
  - dist: wheel, gzipped tarball

## Design decisions

- Python code packaged as a single `webcheck` package + top level `__main__.py` for CLI entry points.
- Zero install for development runs. Wheel packaging with `poetry build`
- [typer](https://github.com/tiangolo/typer) for CLI
- fully type hinted [PEP 484](https://www.python.org/dev/peps/pep-0484/)
- exhaustively linted.
- self contained for ease of evaluation.
- concurrency:
  - asyncio internally 100%. Within a single process, multiple consumers can be configured if it is desired to send data to say postgres and console (my default app does exactly this).
  - multiple instances of consumer and/or producer processes can seamlessly(?) co-operate. Note that all consumer processes should use the same `group_id` and keep in mind the number of partitions configured for the `topic`
- wall clock times are stored explicitly as UTC
- coding approach borrows heavily from functional style with minimal OO - this is a good match with asyncio. The `postgres_writer` for example could be wrapped up in a class to manage connection creation up front.
- exception handling - bail out on exception (see comments re supervisor strategy).

## Production/Future

@todo

Since this is a concept-demo/homework problem this section is to identify some issues that would need to be addressed before considering it for production use.

- supvervisor functionality - there is no inbuilt "restart"
- strategy for dealing with intermittent failures (keep going, restart checker, exit application and leave restart to supervisor, ...)
- credentials, certificates and config management. I have stored the passwords using `keyring`, this is convenient, otherwise the app will fallback to command line, environment variable or prompt the user.
- signal handling or other mechanism for shutting down gracefully.
- deal with errors due to start up - eg there are probably conditions where a duplicate record is read from the topic resulting in key violations.
- changing configurations on the fly eg a management topic for config changes or monitoring zookeeper instance.
- serialization/deserialization of data. For this exercise I used json but protocol-buffers/thrift would probably be more suitable at scale. This would also include connecting the message format schema more robustly with the SQL (or use a document based store)
- source code versioning - make it DRY
- to properly unit test this requires some work with asyncio mock
- decide whether process should automatically create the postgresql assets at start up. Currently there is a CLI command to do this.
- consider adding url specific parameters in config eg check interval.
- logging just uses "root" logger, probably should have its own namespace. It does have the advantage for development at least of being able to control log level for libraries with `--log-level` option.
- figure out how to set kafka topics programmatically.
- the collectors are not generic, ie they return PageMetrics objects. For this exercise it reduces type related codeing errors (very handy for this exercise) but a collector with "Any" as return value type would form the basis of a very generic, reusable system. See also the comments re Protocol Buffers for serialization.

## Credits

I referenced various repos/docs including:

- [aiven.io](https://aiven.io)
- [aoikafka](https://aiokafka.readthedocs.io/en/stable/)
- [aiohttp](https://docs.aiohttp.org/en/stable/)
- various kafka docs
- [postresql](https://www.postgresql.org/)
