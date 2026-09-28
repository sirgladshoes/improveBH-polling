import os
import json
import libsql_client

#turso_url = os.environ["TURSO_DATABASE_URL"]
#turso_token = os.environ["TURSO_AUTH_TOKEN"]


turso_url = os.environ["TURSO_DATABASE_URL"]
turso_token = os.environ["TURSO_AUTH_TOKEN"]

def create_table(table:str):
    con.execute("CREATE TABLE IF NOT EXISTS " + table)

def check_tables():
    tables = con.execute("SELECT name from sqlite_master")
    print(tables.rows)

def has_player(bhID:int)->bool:
    unformated_ids = con.execute("SELECT bhID FROM trackedPlayers WHERE bhID="+str(bhID))
    ids = [n[0] for n in unformated_ids.rows]
    return (bhID in ids)

def insert_tracked_player(bhID: int):
    con.execute("INSERT INTO trackedPlayers VALUES ("+str(bhID)+")")


def get_replay_batch(replay_id, timestamp, replay_data) -> list:
    result = []

    player_data = replay_data["players"]
    is_online = replay_data["game_data"]["isOnline"]
    gamemode = replay_data["game_data"].get("playlistName", None)

    result.append(("INSERT OR IGNORE INTO replays VALUES (?, ?, ?, ?)", (replay_id, timestamp, bool(is_online), gamemode)))

    for player in player_data:
        player_id = player_data[player].get("playerID", False)
        if player_id:
            result.append(("INSERT OR IGNORE INTO replayPlayers VALUES (?, ?, ?, ?, ?)", 
            (replay_id, player_id, json.dumps(player_data[player]["legends"]), player_data[player].get("placement", None), player_data[player].get("deaths", None))))
    return result

def insert_batch(batch: list):
    con.batch(batch)

def fetch_general_player_data(bhID:int):
    result = []
    data = con.execute("SELECT * FROM playerSnapshots WHERE bhID="+str(bhID)+" ORDER BY timestamp DESC").rows
    names = con.execute("SELECT * FROM playerNames WHERE bhID="+str(bhID)+" ORDER BY timestamp DESC").rows
    for p in data:
        subDic = {}
        subDic["bhID"] = p[0] 
        subDic["timestamp"] = p[1] 
        subDic["gameTime"] = p[2] 
        subDic["level"] = p[3] 
        subDic["games"] = p[4]
        subDic["wins"] = p[5]
        n = 0
        while n<len(names)-1 and names[n][1] > p[1]:
            n+=1
        subDic["name"] = names[n][2]
        result.append(subDic)

    return result

def fetch_legend_data(bhID:int):
    result = []
    return result

def fetch_matchup_data_old(bhID:int):
    result = {}
    replayIDs = con.execute("SELECT rp2.legends, rp1.placement AS player_placement,  FROM replayPlayers WHERE bhID="+str(bhID)).rows


    for id_ in replayIDs:
        id = id_[0]
        placement = 2
        players = con.execute("SELECT * FROM replayPlayers WHERE replayID=?", (str(id), )).rows
        for player in players:
            if (player[1] == bhID):
                placement=player[3]
        for player in players:
            if (player[1] != bhID and player[3]!=placement):
                legends = json.loads(player[2])
                for legend in legends:
                    if not (legend in result.keys()):
                        result[legend] = {"games":0, "wins":0}
                    result[legend]["games"] += 1
                    if placement>player[3]:
                        result[legend]["wins"] += 1

    order = sorted(result, key=lambda legend: result[legend]["wins"]/result[legend]["games"])
    sorted_result = []
    for id in order:
        sorted_result.append({"legend_id":id, "games":result[id]["games"], "wins":result[id]["wins"]})
    return sorted_result


def fetch_matchup_data(bhID: int):
    query = """
        SELECT
            rp2.legends,
            rp1.placement AS player_placement,
            rp2.placement AS opponent_placement
        FROM replayPlayers rp1
        JOIN replayPlayers rp2
            ON rp1.replayID = rp2.replayID
        WHERE rp1.bhID = ?
          AND rp2.bhID != ?
          AND rp2.placement != rp1.placement
    """

    rows = con.execute(query, (bhID, bhID)).rows

    result = {}
    for legends_json, player_placement, opponent_placement in rows:
        legends = json.loads(legends_json)

        for legend in legends:
            if legend not in result:
                result[legend] = {"games": 0, "wins": 0}

            result[legend]["games"] += 1

            if player_placement > opponent_placement:
                result[legend]["wins"] += 1

    order = sorted(result, key=lambda legend: result[legend]["wins"]/result[legend]["games"])
    sorted_result = []
    for id in order:
        sorted_result.append({"legend_id":id, "games":result[id]["games"], "wins":result[id]["wins"]})
    return sorted_result

def insert_general_api_data(timestamp, data:dict):
    bhID = data["brawlhalla_id"]

    con.execute("INSERT INTO playerSnapshots VALUES (?, ?, ?, ?, ?, ?)", (bhID, timestamp, data["game_time"], data["level"], data["games"], data["wins"]))
    for legend in data["legends"]:
        con.execute("INSERT INTO legendSnapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
            (bhID, timestamp, legend["id"], legend["games"], legend["wins"], legend["damage_dealt"], legend["damage_taken"], legend["kos"], legend["falls"], legend["match_time"]))
    for weapon in data["weapons"]:
        con.execute("INSERT INTO weaponSnapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
            (bhID, timestamp, weapon["name"], weapon["games"], weapon["wins"], weapon["damage"], weapon["kos"], weapon["time_held"]))

def insert_ranked_api_data(timestamp, data:dict):
    bhID = data["brawlhalla_id"]
    con.execute("INSERT INTO rankedPlayerSnapshots VALUES (?, ?, ?, ?, ?, ?, ?)", 
                (bhID, timestamp, data["games"], data["wins"], data["rating"], data["tier"], data["global_rank"]))
    for legend in data["legends"]:
        con.execute("INSERT INTO rankedLegendSnapshots VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (bhID, timestamp, legend["legend_id"], legend["games"], legend["wins"], legend["rating"], legend["tier"]))

def fetch_tracked_players() -> list:
    result = []
    users = con.execute("SELECT * FROM trackedPlayers")
    for row in users.rows:
        result.append(row[0])
    return result


def init_tables():
    global con
    con = libsql_client.create_client_sync(turso_url, auth_token=turso_token)
    create_table("trackedPlayers(bhID INTEGER UNIQUE)")

    create_table("replays(replayID TEXT UNIQUE, timestamp INTEGER, isOnline BOOLEAN, gameModeName TEXT)")
    create_table("replayPlayers(replayID TEXT, bhID INTEGER, legends, placement INTEGER, deaths INTEGER, UNIQUE (replayID, bhID))")

    create_table("playerSnapshots(bhID INTEGER, timestamp INTEGER, gameTime INTEGER, level INTEGER, games INTEGER, wins INTEGER)")
    create_table("legendSnapshots(bhID INTEGER, timestamp INTEGER, legID INTEGER, games INTEGER, wins INTEGER, damageDealt INTEGER, damageTaken INTEGER, kos INTEGER, falls INTEGER, matchtime INTEGER)")
    create_table("weaponSnapshots(bhID INTEGER, timestamp INTEGER, weapon TEXT, games INTEGER, wins INTEGER, damageDealt INTEGER, kos INTEGER, timeHeld INTEGER)")

    create_table("rankedPlayerSnapshots(bhID INTEGER, timestamp INTEGER, games INTEGER, wins INTEGER, rating INTEGER, tier TEXT, globalRank INTEGER)")
    create_table("rankedLegendSnapshots(bhID INTEGER, timestamp INTEGER, legID INTEGER, games INTEGER, wins INTEGER, rating INTEGER, tier TEXT)")

def close():
    con.close()
#init_tables()

id = 55428652
#print(fetch_matchup_data(id))
#insert_general_api_data(id, 20, main.get_general_player_data(id))
#insert_replay(id, "hash_id", replay_reader.test_replay())
#get_test()
#test = cur.execute("SELECT * FROM replayPlayers")
#print(test.fetchall())
#test = cur.execute("SELECT * FROM playerNames")
#print(test.fetchall())
#get_test()
#con.close() 