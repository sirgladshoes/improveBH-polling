import database
import requests
import time


stats_url = "https://api.brawlhalla.com/v1/player/stats"
legends_url = "https://api.brawlhalla.com/v1/static/legends"
legend_lookup = {legend["legend_id"]: legend for legend in requests.get(legends_url,params={"max_results": 100}).json()["legends"]}

def get_general_player_data(bhid:int):
    player_data_response = requests.get(
        stats_url,
        params={"brawlhalla_id": bhid}
    )

    player_data = {"brawlhalla_id":bhid, "name":"No Data", "wins":0, "games":0, "level":0, "legends":[], "weapons": []}

    response_data = player_data_response.json()

    for key in player_data.keys():
        if key == "legends":
            player_data[key] = generate_legend_data(response_data["legends"], legend_lookup)
        elif key == "weapons":
            player_data[key] = generate_weapon_data(response_data["legends"], legend_lookup)
        else:
            player_data[key] = response_data[key]


    game_time = 0
    for legend in player_data["legends"]:
        game_time += legend["match_time"]
    player_data["game_time"] = game_time

    return player_data


def generate_legend_data(data:list, lookup:dict) -> list:

    data.sort(key=lambda legend: legend.get("match_time", 0), reverse=True)


    result = []
    for legend in data:
        leg_id = legend["legend_id"]
        if leg_id in lookup.keys():
            result.append({"id":leg_id, "games":legend["games"], "wins":legend["wins"],
                "damage_dealt":legend["damage_dealt"], "damage_taken":legend["damage_taken"], 
                "kos":legend["kos"], "falls":legend["falls"], "match_time":legend["match_time"], 
                "damage_w1": legend["damage_weapon_one"], "damage_w2": legend["damage_weapon_two"],
                "kos_w1": legend["ko_weapon_one"], "kos_w2": legend["ko_weapon_two"]
                           })

    return result


def generate_weapon_data(data:list, lookup:dict) -> list:
    empty_weapon_data = {"damage":0, "kos":0, "time_held":0, "games":0, "wins":0}

    result = {}

    result["Unarmed"] = empty_weapon_data.copy()
    for legend in data:
        if legend["legend_id"] in lookup:
            wep_one = lookup[legend["legend_id"]]["weapon_one"]
            wep_two = lookup[legend["legend_id"]]["weapon_two"]

            if not wep_one in result:
                result[wep_one] = empty_weapon_data.copy()
            if not wep_two in result:
                result[wep_two] = empty_weapon_data.copy()


    for legend in data:
        if legend["legend_id"] in lookup:
            wep_one = lookup[legend["legend_id"]]["weapon_one"]
            wep_two = lookup[legend["legend_id"]]["weapon_two"]

            result["Unarmed"]["damage"] += legend["damage_unarmed"]
            result[wep_one]["damage"] += legend["damage_weapon_one"]
            result[wep_two]["damage"] += legend["damage_weapon_two"]

            result["Unarmed"]["time_held"] += (legend["match_time"] - (legend["time_held_weapon_one"] + legend["time_held_weapon_two"]))
            result[wep_one]["time_held"] += legend["time_held_weapon_one"]
            result[wep_two]["time_held"] += legend["time_held_weapon_two"]

            result["Unarmed"]["kos"] += legend["ko_unarmed"]
            result[wep_one]["kos"] += legend["ko_weapon_one"]
            result[wep_two]["kos"] += legend["ko_weapon_two"]

            result["Unarmed"]["games"] += legend["games"]
            result[wep_one]["games"] += legend["games"]
            result[wep_two]["games"] += legend["games"]
 
            result["Unarmed"]["wins"] += legend["wins"]
            result[wep_one]["wins"] += legend["wins"]
            result[wep_two]["wins"] += legend["wins"]

    return [{"name":w, **result[w]} for w in result]


def get_ranked_data(bhid: int) -> dict:
    result = {}
    player_data_response = requests.get(
            stats_url,
            params={"brawlhalla_id": bhid, "mode":"ranked_1v1"},
            timeout=5
        )
    if player_data_response.ok:
        result = player_data_response.json()

    return result



database.init_tables()
tracked_players = database.fetch_tracked_players()
print(tracked_players)
cooldown = 10
for player in tracked_players:
    current = get_general_player_data(int(player))
    database.insert_general_api_data(int(time.time()), current)
    time.sleep(cooldown)

for player in tracked_players:
    current_ranked = get_ranked_data(int(player))
    if current_ranked: database.insert_ranked_api_data(int(time.time()), current_ranked)
    time.sleep(cooldown)

database.close()