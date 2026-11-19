from datetime import datetime, timedelta
from unittest.mock import patch

from behave import then, when

from app.services import sessions
from sessions import PROFILE, assert_unauthorized

ACTIVITY = "/api/v1/auth/practice-activity"


def notice(context, at, marker=None):
    with patch.object(sessions, "utc_now", return_value=at):
        return context.client.post(ACTIVITY, headers=context.headers, json={
            "noticeId": marker if marker is not None else int(at.timestamp() * 1000),
        })


def confirmed_deadline(response):
    assert response.status_code == 200, response.text
    return datetime.fromisoformat(response.json()["idleExpiresAt"])


@when("a practice notice arrives 14 minutes after login")
def first_notice(context):
    context.first_at = context.now + timedelta(minutes=14)
    context.first_result = notice(context, context.first_at)


@then("its confirmed idle deadline is 29 minutes after login")
def check_confirmation(context):
    context.deadline = context.now + timedelta(minutes=29)
    assert confirmed_deadline(context.first_result) == context.deadline


@then("a new notice 30 seconds later does not extend it")
def check_throttle(context):
    assert confirmed_deadline(notice(context, context.first_at + timedelta(seconds=30))) == context.deadline


@then("repeating the original notice two minutes later does not extend it")
def check_duplicate(context):
    for delay in (0, 30):
        marker = int((context.first_at + timedelta(seconds=delay)).timestamp() * 1000)
        assert confirmed_deadline(notice(context, context.first_at + timedelta(minutes=2), marker)) == context.deadline


@then("polling before that deadline succeeds but activity at it is rejected")
def check_idle_boundary(context):
    with patch.object(sessions, "utc_now", return_value=context.deadline - timedelta(seconds=1)):
        assert context.client.get(PROFILE, headers=context.headers).status_code == 200
    assert_unauthorized(notice(context, context.deadline))


@when("practice activity continues until one minute before absolute expiry")
def continue_until_absolute(context):
    context.absolute = context.now + timedelta(hours=24)
    for minute in [*range(14, 1440, 14), 1439]:
        context.activity = notice(context, context.now + timedelta(minutes=minute))
        assert context.activity.status_code == 200, context.activity.text


@then("the confirmed deadline is capped and a notice at absolute expiry is rejected")
def check_absolute(context):
    assert confirmed_deadline(context.activity) == datetime.fromisoformat(
        context.activity.json()["absoluteExpiresAt"]
    ) == context.absolute
    assert_unauthorized(notice(context, context.absolute))


@then("a delayed notice received before expiry uses the server receipt time")
def delayed_notice(context):
    marker = int((context.now + timedelta(minutes=10)).timestamp() * 1000)
    context.received = context.now + timedelta(minutes=14)
    assert confirmed_deadline(notice(context, context.received, marker)) == context.received + timedelta(minutes=15)


@then("a newer notice at the minute boundary extends idle once")
def accepted_at_minute(context):
    received = context.received + timedelta(minutes=1)
    assert confirmed_deadline(notice(context, received)) == received + timedelta(minutes=15)


@then("content is not accepted in an activity notice")
def reject_content(context):
    with patch.object(sessions, "utc_now", return_value=context.received + timedelta(minutes=2)):
        response = context.client.post(ACTIVITY, headers=context.headers, json={
            "noticeId": int(context.received.timestamp() * 1000), "typed": "fixture",
        })
    assert response.status_code == 422, response.text


@then("a practice notice is rejected")
def invalid_notice(context):
    response = context.client.post(ACTIVITY, headers=context.headers, json={
        "noticeId": int(context.now.timestamp() * 1000),
    })
    assert_unauthorized(response)
