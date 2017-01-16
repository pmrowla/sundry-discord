#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''KPS strim discord bot'''

import os
import xml.etree.ElementTree as ET
from datetime import datetime

from discord.ext import commands

from oauthlib.oauth2 import (
    BackendApplicationClient,
    TokenExpiredError,
)

from requests_oauthlib import OAuth2Session
import requests

from pyshorteners import Shortener

import pytz
from dateutil.parser import parse


bot = commands.Bot(command_prefix='.', description='Sundry strim bot')
kps_client_id = os.environ.get('KPS_STRIM_CLIENT', 'client')
kps_client_secret = os.environ.get('KPS_STRIM_SECRET', 'secret')
google_api_key = os.environ.get('GOOGLE_API_KEY', None)

KR_TZ = pytz.timezone('Asia/Seoul')


def short_url(url):
    key = google_api_key
    if key:
        googl = Shortener(
            'Google',
            api_key=key
        )
        return googl.short(url)
    else:
        return url


def format_timedelta(td):
    strs = []
    if td.days:
        if td.days > 1:
            strs.append('{} days'.format(td.days))
        else:
            strs.append('{} day'.format(td.days))
    (hours, seconds) = divmod(td.seconds, 3600)
    if hours:
        if hours > 1:
            strs.append('{} hours'.format(hours))
        else:
            strs.append('{} hour'.format(hours))
    (minutes, seconds) = divmod(seconds, 60)
    if minutes:
        if minutes > 1:
            strs.append('{} minutes'.format(minutes))
        else:
            strs.append('{} minute'.format(minutes))
    if seconds:
        if seconds > 1:
            strs.append('{} seconds'.format(seconds))
        else:
            strs.append('{} second'.format(seconds))
    return ', '.join(strs)


def _configure_kps():
    bot.kps = {}
    client = BackendApplicationClient(client_id=kps_client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(
        'https://strim.pmrowla.com/o/token/',
        client_id=kps_client_id,
        client_secret=kps_client_secret,
    )
    bot.kps['token'] = token


def kps_strim_get(url):
    def save_token(token):
        bot.kps['token'] = token

    client = BackendApplicationClient(client_id=kps_client_id)
    oauth = OAuth2Session(
        client=client,
        token=bot.kps['token']
    )
    try:
        r = oauth.get(url)
    except TokenExpiredError:
        token = oauth.fetch_token(
            'https://strim.pmrowla.com/o/token/',
            client_id=kps_client_id,
            client_secret=kps_client_secret,
        )
        bot.kps['token'] = token
        r = oauth.get(url)
    r.raise_for_status()
    return r


def _next_strim():
    msgs = []
    data = kps_strim_get(
        'https://strim.pmrowla.com/api/v1/strims/?format=json'
    ).json()
    if data['count']:
        strim = data['results'][0]
        title = strim.get('title')
        timestamp = parse(strim.get('timestamp'))
        channel_name = strim.get('channel', {}).get('name')
        slug = strim.get('slug')
        td = timestamp - pytz.utc.localize(datetime.utcnow())
        msgs.append('Next strim in {}'.format(
            format_timedelta(td),
        ))
        msgs.append('{} - {}: {}'.format(
            timestamp.astimezone(KR_TZ).strftime('%Y-%m-%d %H:%M KST'),
            channel_name,
            title,
        ))
        msgs.append(
            short_url(
                'https://strim.pmrowla.com/strims/{}/'.format(slug)
            )
        )
    else:
        msgs.append('No scheduled strims')
    return msgs


def _check_live(notify=True):
    live = bot.kps.get('live', False)
    url = 'https://secure.pmrowla.com/live'
    params = {'app': 'strim'}
    r = requests.get(url, params=params)
    r.raise_for_status()
    msgs = []
    root = ET.fromstring(r.text)
    if root.find('.//active') is not None:
        if not live and notify:
            msgs.append('Strim is now live')
            msgs.append(short_url('https://strim.pmrowla.com/'))
        bot.kps['live'] = True
    else:
        if live and notify:
            msgs.append('Strim finished')
            msgs.extend(_next_strim())
        bot.kps['live'] = False
    return msgs


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('-----')


@bot.command()
async def strim():
    """Fetch next strim"""
    _check_live(notify=False)
    msgs = []
    if bot.kps['live']:
        msgs.append('Strim is live')
        msgs.append(short_url('https://strim.pmrowla.com/'))
    else:
        msgs.append('Strim is down')
        msgs.extend(_next_strim())
    if msgs:
        print(' | '.join(msgs))
        await bot.say(' | '.join(msgs))


_configure_kps()
bot.run(os.environ.get('SUNDRY_BOT_TOKEN', 'token'))
