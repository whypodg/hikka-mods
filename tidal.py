#          █   █ █ █ ▀▄▀ █▀█ █▀█ ▄▄█ █▀▀
#          ▀▄▀▄▀ █▀█  █  █▀▀ █▄█ █▄█ █▄█ ▄
#                © Copyright 2023
#
#              https://t.me/whypodg
#
# 🔒 Licensed under CC-BY-NC-ND 4.0
# 🌐 https://creativecommons.org/licenses/by-nc-nd/4.0

# meta developer: @whypodg
# scope: hikka_only
# scope: hikka_min 1.6.3
# requires: tidalapi


import asyncio
import base64
import io
import json
import logging
import requests

import tidalapi
import tidalapi.media as media
from telethon import types

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)


@loader.tds
class TidalMod(loader.Module):
	"""API wrapper over TIDAL Hi-Fi music streaming service"""

	strings = {
		"name": "Tidal",
		"_cfg_quality": "Select the desired quality for the tracks",
		"args": "<emoji document_id=5312526098750252863>❌</emoji> <b>Specify search query</b>",
		"404": "<emoji document_id=5312526098750252863>❌</emoji> <b>No results found</b>",
		"oauth": (
			"🔑 <b>Login to TIDAL</b>\n\n<i>This link will expire in 5 minutes</i>"
		),
		"oauth_btn": "🔑 Login",
		"success": "✅ <b>Successfully logged in!</b>",
		"error": "❌ <b>Error logging in</b>",
		"search": "<emoji document_id=5370924494196056357>🖤</emoji> <b>{name}</b>\n<emoji document_id=6334768915524093741>⏰</emoji> <b>Release date (in Tidal):</b> <i>{release}</i>",
		"downloading_file": "\n\n<i>Downloading audio…</i>",
		"searching": "<emoji document_id=5309965701241379366>🔍</emoji> <b>Searching...</b>",
		"auth_first": "<emoji document_id=5312526098750252863>❌</emoji> <b>You need to login first</b>"
	}

	strings_ru = {
		"_cfg_quality": "Выберите желаемое качество для треков",
		"args": "<emoji document_id=5312526098750252863>❌</emoji> <b>Укажите поисковый запрос</b>",
		"404": "<emoji document_id=5312526098750252863>❌</emoji> <b>Ничего не найдено</b>",
		"oauth": (
			"🔑 <b>Авторизуйтесь в TIDAL</b>\n\n<i>Эта ссылка будет действительна в"
			" течение 5 минут</i>"
		),
		"oauth_btn": "🔑 Авторизоваться",
		"success": "✅ <b>Успешно авторизованы!</b>",
		"error": "❌ <b>Ошибка авторизации</b>",
		"search": "<emoji document_id=5370924494196056357>🖤</emoji> <b>{name}</b>\n<emoji document_id=6334768915524093741>⏰</emoji> <b>Дата релиза (в Tidal):</b> <i>{release}</i>",
		"downloading_file": "\n\n<i>Загрузка аудио…</i>",
		"searching": "<emoji document_id=5309965701241379366>🔍</emoji> <b>Ищем...</b>",
		"auth_first": "<emoji document_id=5312526098750252863>❌</emoji> <b>Сначала нужно авторизоваться</b>"
	}


	def __init__(self):
		self.qs = {
			"Normal": "LOW",
			"High": "HIGH",
			"HiFi": "LOSSLESS",
			"Master": "HI_RES"
		}
		self.fs = {
			"Normal": "mp3",
			"High": "m4a",
			"HiFi": "flac",
			"Master": "flac"
		}
		self.config = loader.ModuleConfig(
			loader.ConfigValue(
				"quality",
				"HiFi",
				lambda: self.strings["_cfg_quality"],
				validator=loader.validators.Choice(["Normal", "High", "HiFi", "Master"]),
			)
		)


	async def client_ready(self):
		self._faved = []

		self.tidal = tidalapi.Session()
		login_credentials = (
			self.get("session_id"),
			self.get("token_type"),
			self.get("access_token"),
			self.get("refresh_token"),
		)

		if all(login_credentials):
			try:
				self.tidal.load_oauth_session(*login_credentials)
				assert self.tidal.check_login()
			except Exception:
				logger.exception("Error loading OAuth session")

		self._obtain_faved.start()


	@loader.loop(interval=60)
	async def _obtain_faved(self):
		if not self.tidal.check_login():
			return

		self._faved = list(
			map(
				int,
				(
					await utils.run_sync(
						self.tidal.request.request,
						"GET",
						f"users/{self.tidal.user.id}/favorites/ids",
					)
				).json()["TRACK"],
			)
		)


	def _save_session_info(self):
		self.set("token_type", self.tidal.token_type)
		self.set("session_id", self.tidal.session_id)
		self.set("access_token", self.tidal.access_token)
		self.set("refresh_token", self.tidal.refresh_token)


	@loader.command(
		ru_doc="Авторизация в TIDAL"
	)
	async def tlogincmd(self, message: types.Message):
		"""Open OAuth window to login into TIDAL"""
		result, future = self.tidal.login_oauth()
		form = await self.inline.form(
			message=message,
			text=self.strings("oauth"),
			reply_markup={
				"text": self.strings("oauth_btn"),
				"url": f"https://{result.verification_uri_complete}",
			},
			gif="https://0x0.st/oecP.MP4",
		)

		outer_loop = asyncio.get_event_loop()

		def callback(*args, **kwargs):
			nonlocal form, outer_loop
			if self.tidal.check_login():
				asyncio.ensure_future(
					form.edit(
						self.strings("success"),
						gif="https://c.tenor.com/IrKex2lXvR8AAAAC/sparkly-eyes-joy.gif",
					),
					loop=outer_loop,
				)
				self._save_session_info()
			else:
				asyncio.ensure_future(
					form.edit(
						self.strings("error"),
						gif="https://i.gifer.com/8Z2a.gif",
					),
					loop=outer_loop
				)

		future.add_done_callback(callback)


	@loader.command(
		ru_doc="<запрос> - Поиск трека в TIDAL"
	)
	async def tidalcmd(self, message: types.Message):
		"""<query> - Search TIDAL"""

		if not await utils.run_sync(self.tidal.check_login):
			await utils.answer(message, self.strings("auth_first"))
			return

		query = utils.get_args_raw(message)
		if not query:
			await utils.answer(message, self.strings("args"))
			return

		message = await utils.answer(message, self.strings("searching"))

		result = self.tidal.search(query=query)
		if not result or not result['tracks']:
			await utils.answer(message, self.strings("404"))
			return

		track = result['tracks'][0]
		track_res = {
			"url": None, "id": track.id,
			"artists": [], "name": track.name,
			"tags": [], "duration": track.duration
		}

		meta = (
			self.tidal.request.request(
				"GET",
				f"tracks/{track_res['id']}",
			)
		).json()
		logger.error(str(meta))

		artists = track_res['artists']
		for i in meta["artists"]:
			if i['name'] not in artists:
				artists.append(i['name'])
		full_name = f"{', '.join(artists)} - {track_res['name']}"

		tags = track_res['tags']
		if meta.get("explicit"):
			tags += ["#explicit🤬"]
		if isinstance(meta.get("audioModes"), list):
			for tag in meta["audioModes"]:
				tags += [f"#{tag}🎧"]
		if track_res['id'] in self._faved:
			tags += ["#favorite🖤"]
		if tags:
			track_res['tags'] = tags

		text = self.strings("search").format(
			name=utils.escape_html(full_name),
			release=track.tidal_release_date.strftime(
				"%d.%m.%Y"
			)
		)
		message = await utils.answer(
			message, text + self.strings("downloading_file")
		)

		t = self.tidal.request.request(
			"GET",
			f"tracks/{track_res['id']}/playbackinfopostpaywall",
			{
				"audioquality": self.qs.get(self.config['quality'], "HI_RES"),
				"playbackmode": "STREAM",
				"assetpresentation": "FULL"
			}
		).json()
		man = json.loads(base64.b64decode(t['manifest']).decode('utf-8'))
		track_res['url'] = man['urls'][0]
		track_res['tags'].append(f"#{self.qs.get(self.config['quality'], 'HI_RES')}🔈")

		with requests.get(track_res['url']) as r:
			audio = io.BytesIO(r.content)
			audio.name = f"audio.{self.fs.get(self.config['quality'], 'mp3')}"
			audio.seek(0)

		text += f"\n\n{', '.join(track_res['tags'])}"
		text += f"\n\n<emoji document_id=5359582743992737342>🎵</emoji> " \
				f"<b><a href='https://tidal.com/browse/track/{track_res['id']}'>Tidal</a></b>"

		await utils.answer_file(
			message, audio, text,
			attributes=([
				types.DocumentAttributeAudio(
					duration=track_res['duration'],
					title=track_res['name'],
					performer=', '.join(track_res['artists'])
				)
			])
		)