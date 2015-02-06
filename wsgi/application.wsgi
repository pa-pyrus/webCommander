#!/usr/bin/python
# vim:fileencoding=utf-8:ts=8:et:sw=4:sts=4:tw=79

"""
application.wsgi: Bottle application for the WebCommander REST Service.

Copyright (c) 2015 Pyrus <pyrus at coffee dash break dot at>
See the file LICENSE for copying permission.
"""

from datetime import datetime, timedelta
from inspect import getdoc
from itertools import chain, groupby
from json import dumps

from bottle import Bottle
from bottle import request, response, template, redirect
from bottle.ext import sqlalchemy

from icalendar import Calendar, Event
from pytz import utc as UTC

from database import engine
from database.models import Patch
from database.models import Player, Tournament
from database.models import LeaderBoardEntry, UberAccount
from sqlalchemy.orm.exc import NoResultFound

import trueskill
# default values are fine, let's assume 0.3% draw chance
trueskill.setup(draw_probability=0.003)

from markdown import Markdown

# initialize the app and db plugin
app = application = Bottle()
db_plugin = sqlalchemy.Plugin(engine)
app.install(db_plugin)


@app.route("/api/uberId/<pid:int>")
def handle_api_uberid_by_pid(pid, db):
    """
    Query the official UberId for a specific player.

    This method returns a player's UberId.

    # URL Parameters #
    `pid (int)`
    :   The player's PAStats ID.

    # Response Data #
    `id (int)`
    :   The player's PAStats ID.

    `uberId (int)`
    :   The player's UberId.

    `uberIdString (string)`
    :   The player's UberId as a string.

    # Return Codes #
    `200`
    :   The player was found and corresponding data is returned.

    `404`
    :   No mapping exists for the provided PAStats ID.
        All response values are returned as `null`.

    # Example Request #
        GET /api/uberId/123 HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "id": 123,
            "uberId": 1234567901234567890,
            "uberIdString": "12345678901234567890"
        }
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    invalid_result = {"name": None, "id": None, "rank": None}

    if not pid:
        response.status = "404 Player Not Found"
        return invalid_result

    try:
        uber_acc = db.query(UberAccount).filter(UberAccount.pid == pid).one()
    except NoResultFound:
        response.status = "404 Player Not Found"
        return invalid_result

    return dumps({"id": uber_acc.pid,
                  "uberId": int(uber_acc.uid),
                  "uberIdString": str(uber_acc.uid)}, indent=2)


@app.route("/api/rank/<pid:int>")
def handle_api_rank(pid, db):
    """
    Query rank information for a specific player.

    This method returns a player's current rank and display name.

    # URL Parameters #
    `pid (int)`
    :   The player's PAStats ID.

    # Response Data #
    `id (int)`
    :   The player's PAStats ID.

    `name (string)`
    :   The player's last known display name.

    `rank (int)`
    :   The player's current rank on the UberSkill ladder.

    # Return Codes #
    `200`
    :   The player was found and corresponding data is returned.

    `404`
    :   The player was not found on the UberSkill ladder.
        All response values are returned as `null`.

    # Example Request #
        GET /api/rank/123 HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "id": 123,
            "name": "Dummy User",
            "rank": 456
        }
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    invalid_result = {"name": None, "id": None, "rank": None}

    if not pid:
        response.status = "404 Player Not Found"
        return invalid_result

    try:
        player = db.query(Player).filter(Player.pid == pid).one()
    except NoResultFound:
        response.status = "404 Player Not Found"
        return invalid_result

    cmp_rating = (db.query(Player.rating)
                  .filter(Player.pid == pid)
                  .subquery())
    rank = (db.query(Player.pid)
            .filter(Player.rating > cmp_rating)
            .count())

    return dumps({"name": player.name,
                  "id": player.pid,
                  "rank": 1 + rank}, indent=2)


@app.route("/api/ladder")
def handle_api_ladder(db):
    """
    Query the UberSkill ladder.

    This method returns an array of players in order of ranking.
    The output can be filtered by
    * number of players returned and
    * activity in a certain number of days.

    # Query String #
    `limit (int)`
    :   Restrict the output to a certain number of players.
        If this option is omitted, all players will be returned.

    `activity (int)`
    :   Restrict the output to active players.
        Activity is determined by whether a player has played a match in the
        last N days.
        If this option is omitted, players will not be filtered by activity.

    `uberId (any)`
    :   Include the UberId if it is known.
        The parameter's value is not interpreted, its presence is sufficient.

    # Response Data #
    `id (int)`
    :   The player's PAStats ID.

    `name (string)`
    :   The player's last known display name.

    `uberId (int)`
    :   The player's UberId or `null` if it's unknown.

    # Return Codes #
    `200`
    :   UberSkill ladder is returned.

    # Example Request #
        GET /api/ladder?limit=3&activity=7&uberId HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        [
            {
                "id": 123,
                "name": "Dummy User A",
                "uberId": 1234567890123456789
            },
            {
                "id": 456,
                "name": "Dummy User B",
                "uberId": null
            },
            {
                "id": 789,
                "name": "Dummy User C",
                "uberId": 9876543210987654321
            }
        ]
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    # don't filter anything by default
    limit = request.query.get("limit", default=0, type=int)
    activity = request.query.get("activity", default=0, type=int)
    uber_id = "uberId" in request.query

    if not uber_id:
        top = (db.query(Player.pid, Player.name)
                 .order_by(Player.rating.desc()))
    else:
        top = (db.query(Player.pid, Player.name, UberAccount.uid)
                 .outerjoin(UberAccount, UberAccount.pid == Player.pid)
                 .order_by(Player.rating.desc()))

    if activity > 0:
        activity_deadline = datetime.utcnow() - timedelta(activity)
        top = top.filter(Player.updated >= activity_deadline)

    if limit > 0:
        top = top.limit(limit)

    top = top.all()

    if not uber_id:
        return dumps([{"id": p[0], "name": p[1]} for p in top], indent=2)
    else:
        return dumps([{"id": p[0],
                       "name": p[1],
                       "uberId": int(p[2]) if p[2] else None}
                      for p in top], indent=2)


@app.route("/api/leaderboards")
def handle_api_leaderboards(db):
    """
    Query official Uber Leaderboards.

    This method returns arrays of players in order of ranking for each league.

    # Response Data #
    `uid (int)`
    :   The player's UberId.

    `pid (int)`
    :   The player's PAStats ID or `null` if it's unknown.

    `name (string)`
    :   The player's display name.

    `lastmatchat (string)`
    :   ISO timestamp of when the player last played.

    # Return Codes #
    `200`
    :   LeaderBoards are returned.

    # Example Request #
        GET /api/leaderboards HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "uber":
            [
                {
                    "uid": 1234567890123456789
                    "pid": 123,
                    "name": "Dummy User A",
                    "lastmatchat": "2012-04-28T19:00:00"
                },
                {
                    "uid": 9876543210987654321
                    "pid": null,
                    "name": "Dummy User B",
                    "lastmatchat": "2012-11-11T11:11:00"
                },
                ...
            ],
            "platinum": [...],
            "gold": [...],
            "silver": [...],
            "bronze": [...]
        }
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    entries = (db.query(LeaderBoardEntry.league, LeaderBoardEntry.last,
                        UberAccount.uid, UberAccount.pid, UberAccount.dname)
                 .outerjoin(UberAccount,
                            UberAccount.uid == LeaderBoardEntry.uid)
                 .order_by(LeaderBoardEntry.league, LeaderBoardEntry.rank)
                 .all())

    leaderboards = dict()
    for league, group in groupby(entries, key=lambda e: e[0]):
        subentries = [{"uid": int(e[2]),
                       "pid": int(e[3]) if e[3] else None,
                       "name": e[4],
                       "lastmatchat": e[1].isoformat()} for e in group]
        leaderboards[league.lower()] = subentries

    return dumps(leaderboards, indent=2)


@app.route("/api/leaderboard/<league:re:uber|platinum|gold|silver|bronze>")
def handle_api_leaderboard(league, db):
    """
    Query an official Uber Leaderboard.

    This method returns an array of players in order of ranking for the
    specified league.

    # URL Parametrs #
    `league (string)`
    :   The league to query.
        Allowed values are: `uber`, `platinum`, `gold`, `silver`, `bronze`

    # Response Data #
    `uid (int)`
    :   The player's UberId.

    `pid (int)`
    :   The player's PAStats ID or `null` if it's unknown.

    `name (string)`
    :   The player's display name.

    `lastmatchat (string)`
    :   ISO timestamp of when the player last played.

    # Return Codes #
    `200`
    :   LeaderBoards are returned.

    # Example Request #
        GET /api/leaderboard/uber HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        [
            {
                "uid": 1234567890123456789
                "pid": 123,
                "name": "Dummy User A",
                "lastmatchat": "2012-04-28T19:00:00"
            },
            {
                "uid": 9876543210987654321
                "pid": null,
                "name": "Dummy User B",
                "lastmatchat": "2012-11-11T11:11:00"
            },
            ...
        ]
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    entries = (db.query(LeaderBoardEntry.last,
                        UberAccount.uid, UberAccount.pid, UberAccount.dname)
                 .outerjoin(UberAccount,
                            UberAccount.uid == LeaderBoardEntry.uid)
                 .filter(LeaderBoardEntry.league == league.capitalize())
                 .order_by(LeaderBoardEntry.rank)
                 .all())

    return dumps([{"uid": int(e[1]),
                   "pid": int(e[2]) if e[2] else None,
                   "name": e[3],
                   "lastmatchat": e[0].isoformat()} for e in entries],
                 indent=2)


@app.route("/api/quality")
def handle_api_quality(db):
    """
    Query match quality for the matchup between any combination of players.

    This method returns all player's display name and the estimated match
    quality.

    # Request Data #
    This method expects a JSON-encoded array of arrays containing the PA Stats
    IDs of each participating player. Each inner array represents a team and
    has to contain at least one item.

    # Response Data #
    `quality (float)`
    :   The match quality.
        The nearer this value is to `1.0` the more balanced the match is deemed
        to be.

    `teams (array)`
    :   An array of arrays, with each nested array containing the following
        information on players.

        `id (int)`
        :   The player's PAStats ID.

        `name (string)`
        :   The player's last known display name.

    # Return Codes #
    `200`
    :   UberSkill ladder is returned.

    `400`
    :   The request (data) was malformed.

    `404`
    :   The player was not found on the UberSkill ladder.
        All response values are returned as `null`.

    `500`
    :   The request (data) was malformed.

    # Example Request #
        GET /api/quality HTTP/1.1
        Host: pa.coffee-break.at
        Content-Type: application/json

        [
            [12, 34],
            [56]
        ]

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "quality": 0.5,
            "teams":
                [
                    [
                        {
                            "id": 12,
                            "name": "Dummy User A"
                        },
                        {
                            "id": 34,
                            "name": "Dummy User B"
                        }
                    ],
                    [
                        {
                            "id": 56,
                            "name": "Dummy User C"
                        },
                    ]
                ]
        }
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    invalid_result = {"quality": None, "teams": None}

    teams_request = request.json
    if type(teams_request) is not list:
        response.status = "400 Invalid Request"
        return invalid_result

    # create player lists and rating groups
    teams = list()
    rating_groups = list()
    for team in teams_request:
        if type(team) is not list:
            response.status = "400 Invalid Request"
            return invalid_result

        try:
            players = [db.query(Player).filter(Player.pid == pid).one()
                       for pid in team]
        except NoResultFound:
            response.status = "404 Player Not Found"
            return invalid_result

        teams.append([{"name": player.name,
                       "id": player.pid} for player in players])
        rating_groups.append([player.skill for player in players])

    # calculate quality and build return value
    quality = trueskill.quality(rating_groups)

    return dumps({"quality": quality,
                  "teams": teams}, indent=2)


@app.route("/api/forecast/<pid1:int>~<pid2:int>")
def handle_api_forecast_old(pid1, pid2, db):
    """
    Query match quality and favourite in the matchup between two players.

    This method returns both players' display name, the favoured player and
    the estimated match quality.

    # URL Parameters #
    `pid1 (int)`
    :   The first player's PAStats ID.

    `pid2 (int)`
    :   The second player's PAStats ID.

    # Response Data #
    `player1`
    :   `id`
        :   The first player's PAStats ID.

        `name`
        :   The first player's last known display name.

    `player2`
    :   `id`
        :   The second player's PAStats ID.

        `name`
        :   The second player's last known display name.

    `favourite`
    :   `id`
        :   The favoured player's PAStats ID.

        `name`
        :   The favoured player's last known display name.

    `quality`
    :   The estimated match quality.

    # Return Codes #
    `200`
    :   Both players were found and corresponding data is returned.

    `404`
    :   At least one player was not found on the UberSkill ladder.
        All response values are returned as `null`.

    # Example Request #
        GET /api/forecast/123~456 HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        {
            "player1": {
                "id": 123,
                "name": "Dummy User A"
            },
            "player2": {
                "id": 456,
                "name": "Dummy User B"
            },
            "favourite": {
                "id": 123,
                "name": "Dummy User A"
            },
            "quality": 0.91
        }
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    invalid_result = {"name": None, "id": None, "rank": None}

    if not pid1 or not pid2 or pid1 == pid2:
        response.status = "404 Player Not Found"
        return invalid_result

    try:
        player1 = db.query(Player).filter(Player.pid == pid1).one()
        player2 = db.query(Player).filter(Player.pid == pid2).one()
    except NoResultFound:
        response.status = "404 Player Not Found"
        return invalid_result

    quality = trueskill.quality_1vs1(player1.skill, player2.skill)

    if player1.rating > player2.rating:
        favourite = {"name": player1.name, "id": player1.pid}
    elif player2.rating > player1.rating:
        favourite = {"name": player2.name, "id": player2.pid}
    else:
        favourite = None

    return dumps({"player1": {"name": player1.name, "id": player1.pid},
                  "player2": {"name": player2.name, "id": player2.pid},
                  "quality": quality, "favourite": favourite})


@app.route("/api/builds")
def handle_api_builds(db):
    """
    Query current build versions as provided by the Uberent patcher webservice.

    This method returns all available builds, a short description and the time
    they were last updated.

    # Response Data #
    `name (string)`
    :   The build's name, usually `stable` or `PTE`.

    `desc (string)`
    :   Short description.

    `version (string)`
    :   Latest build version.

    `updated (string)`
    :   ISO timestamp of when the build was last updated.

    # Return Codes #
    `200`
    :   Latest build information is returned.

    # Example Request #
        GET /api/builds HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        [
            {
                "name": "stable",
                "desc": "Latest Stable Build",
                "version": "12345",
                "updated": "2012-04-28T19:00:00"
            },
            {
                "name": "PTE",
                "desc": "Private Test Environment",
                "version": "56789",
                "updated": "2013-02-07T23:00:00"
            }
        ]
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    builds = db.query(Patch).all()

    return dumps([{"name": build.name,
                   "desc": build.description,
                   "version": build.build,
                   "updated": build.updated.isoformat()}
                  for build in builds], indent=2)


@app.route("/api/tournaments")
def handle_api_tournaments(db):
    """
    Query tournaments stored in the tournament-db repository.

    This method returns all known tournaments sorted by scheduled date.

    # Response Data #
    `title (string)`
    :   The tournament's title.

    `date (string)`
    :   ISO timestamp of when the tournament is/was scheduled.

    `winner (string)`
    :   If the tournament is already over, this is the tournament's winner(s).
        Otherwise it is `null`.

    `mode (string)`
    :   Short description of tournament specifics.

    `url (string)`
    :   URL to additional information.


    # Return Codes #
    `200`
    :   All requested tournaments are returned.

    # Example Request #
        GET /api/tournaments HTTP/1.1
        Host: pa.coffee-break.at

    # Example Response #
        HTTP/1.1 200 OK
        Content-Type: application/json

        [
            {
                "title": "Dummy Tourney #1",
                "date": "2012-04-28T19:00:00",
                "winner": "Dummy User",
                "mode": "32 slot 1v1 Double Elimination"
                "url": "http://exmample.com/dummy-tourney-1",
            },
            {
                "title": "Dummy Tourney #2",
                "date": "2013-03-07T23:00:00",
                "winner": null,
                "mode": "16 slot 2v2 Swiss Style"
                "url": "http://exmample.com/dummy-tourney-2",
            }
        ]
    """
    response.set_header("Access-Control-Allow-Origin", "*")
    response.set_header("Content-Type", "application/json")

    tourneys = db.query(Tournament).order_by(Tournament.date).all()

    return dumps([{"title": tourney.title,
                   "date": tourney.date.isoformat(),
                   "winner": tourney.winner,
                   "mode": tourney.mode,
                   "url": tourney.url}
                  for tourney in tourneys], indent=2)


@app.route("/ladder")
def handle_ladder(db):
    """Show the full UberSkill ladder ranking."""
    top = (db.query(Player.name)
           .order_by(Player.rating.desc())
           .all())
    top_list = list(chain(*top))
    return template("ladder", top=top_list)


@app.route("/leaderboards")
def handle_leaderboards(db):
    """Show the official PA Leaderboards."""
    entries = (db.query(LeaderBoardEntry.league, UberAccount.dname)
                 .outerjoin(UberAccount,
                            UberAccount.uid == LeaderBoardEntry.uid)
                 .order_by(LeaderBoardEntry.league, LeaderBoardEntry.rank)
                 .all())

    leaderboards = dict()
    for league, group in groupby(entries, key=lambda e: e[0]):
        subentries = [e[1] for e in group]
        leaderboards[league.lower()] = subentries

    leaderboards = {league: [e[1] for e in group]
                    for league, group in groupby(entries, key=lambda e: e[0])}

    return template("leaderboards", leaderboards=leaderboards)


@app.route("/calendar")
def handle_calendar(db):
    """Show a calendar of past and coming envents."""
    response.set_header("Content-Type", "text/calendar")

    cal = Calendar()
    cal.add("prodid", "-//Pyrus//PA Tournament Calendar//EN")
    cal.add("version", "2.0")

    tourneys = db.query(Tournament).order_by(Tournament.date).all()
    for tourney in tourneys:
        event = Event()
        event.add("uid", "{0}@tournament-db".format(tourney.tid))
        event.add("summary", tourney.title)
        event.add("dtstart", tourney.date.replace(tzinfo=UTC))
        event.add("description", "Mode: {0}\nLink: {1}".format(tourney.mode,
                                                               tourney.url))
        event.add("categories", "Tournament")
        cal.add_component(event)

    return cal.to_ical()


@app.route("/documentation")
def handle_documentation():
    """Show documentation for REST API calls."""
    # only include the following functions
    doc_funcs = (handle_api_uberid_by_pid,
                 handle_api_rank,
                 handle_api_ladder,
                 handle_api_leaderboards,
                 handle_api_leaderboard,
                 handle_api_quality,
                 handle_api_builds,
                 handle_api_tournaments)

    md = Markdown(extensions=["def_list", "headerid(level=2,forceid=False)"],
                  output_format="html5")

    documentation = list()
    for route in app.routes:
        func = route.get_undecorated_callback()
        if func not in doc_funcs:
            continue

        func_title = "{0} {1}".format(route.method, route.rule)

        func_doc = getdoc(func)
        func_html = md.convert(func_doc)
        md.reset()

        documentation.append({"title": func_title, "content": func_html})

    return template("documentation",
                    documentation=documentation)


@app.route("/pamm/<name>")
def handle_pamm_redirect(name):
    """Redirect to pamm:// URLs."""
    pamm_uri = "pamm://{0}".format(name)
    redirect(pamm_uri)
