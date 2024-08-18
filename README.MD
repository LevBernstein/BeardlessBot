# Beardless Bot

### Full Release 2.3.7 ![Coverage badge](./resources/images/coverage.svg) ![Unit tests badge](./resources/images/tests.svg) ![Docstring coverage badge](./resources/images/docstr-coverage.svg) ![flake8 badge](./resources/images/flake8-badge.svg)

A Discord bot supporting gambling (coin flips and blackjack),
a currency system, fun facts, and more.

Originally created for use in eggsoup's Discord server.

If you just want to add the bot to your own Discord
server while I host it, you can simply
[click this link](https://discord.com/api/oauth2/authorize?client_id=654133911558946837&permissions=8&scope=bot),
then skip down to [Setup](#setup).
If you want to run your own instance of Beardless Bot,
follow the steps outlined directly below in [Installation](#installation).


## Installation

1. Download the repository.

2. Download [Python 3](https://python.org/downloads), and then run
`pip3 install -r resources/requirements.txt`. Beardless Bot requires Python
3.10 or newer, and has been tested on 3.10.4, 3.11.9, and 3.12.3. If you are
using python virtualenv, name your virtualenv "venv" and run
`source venv/bin/activate` before running `pip3 install`.

3. Create a file named ".env" in the same directory as Bot.py. Insert
into it the line `DISCORDTOKEN=yourtoken`, where yourtoken is the Discord API
token you get from [here](https://discord.com/developers/applications).

4. As of Full Release v1.3.0, Beardless Bot supports calls to the Brawlhalla
API. If you don't have [an API key](https://dev.brawlhalla.com/), those
commands will simply be disabled; the Bot will work fine. If you do have an
API key, place it in .env as `BRAWLKEY=yourkey`. If you want to fork this repo
and have Brawlhalla commands covered by unit tests, you'll need to define a
repository secret with the name BRAWLKEY. For more information, see
[this guide](https://docs.github.com/en/actions/reference/encrypted-secrets).

5. Run `python3 Bot.py` to start the bot.


## Setup

* To use the !spar command, create a channel named looking-for-spar.

* To use Beardless Bot's event logging, create a channel named bb-log.

* To use special colors, create roles named special red,
special blue, special pink, and special orange.


## Contributing to Beardless Bot

Interested in improving Beardless Bot? Great! If you have an idea, feel
free to open a Pull Request with an explanation of what your changes
accomplish. There are also several issues open in the Issues tab that
could use someone tackling them. Please make sure your code is PEP8
compliant (except for tabs), with a column limit of 80.


## Testing

To run Beardless Bot's suite of unit tests, do `bash unitTests.sh`. This will
also generate a coverage badge. To run an individual test--for instance, the
Muted role creation test--use the pytest command, like so:
`pytest -v bb_test.py::test_createMutedRole`. To run the suite of code quality
tests, do `pytest -v -k quality`.


## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
