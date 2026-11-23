from behave import then

RANKING = "/api/v1/matches/leaderboard"


@then("the ranking {outcome} the player")
def check_ranking(context, outcome):
    assert outcome in {"lists", "does not list"}, outcome
    response = context.client.get(RANKING, headers=context.headers, params={
        "difficulty": "easy", "language": "eng", "limit": 100,
    })
    assert response.status_code == 200, response.text
    listed = context.user_id in [row["userId"] for row in response.json()["entries"]]
    assert listed == (outcome == "lists"), response.json()
