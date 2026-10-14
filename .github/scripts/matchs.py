# Mise à jour quotidienne du site (GitHub Actions, voir .github/workflows/matchs.yml), sans aucun appel à
# PandaScore : les matchs viennent des calendriers publics du serveur d'eSportly (cache du relais).
# 1) « Prochains matchs » sur chaque page d'équipe (fr et en), avec les données « événement sportif » pour Google.
# 2) Les pages « Les matchs de la semaine » dans les 5 langues, fabriquées à partir des pages « Nouveautés ».
# Usage : python3 .github/scripts/matchs.py   (depuis la racine du site)
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

SITE = Path(__file__).resolve().parents[2]
URL = "https://esportly.protojo.fr/"
CAL = "https://lmavqchwevcvvneblqld.supabase.co/functions/v1/calendrier/equipe/"
PARIS = ZoneInfo("Europe/Paris")
NOW = datetime.now(timezone.utc)
START, END = "<!-- prochains-matchs -->", "<!-- /prochains-matchs -->"

LANGS = {
    "fr": dict(file="matchs-de-la-semaine.html", news="nouveautes.html", lang="fr",
               days=["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
               months=["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
               title="Les matchs de la semaine", kicker="Cette semaine",
               lead="Les matchs des grandes équipes d'e-sport pour les 7 prochains jours, mis à jour chaque matin. Heures de Paris.",
               meta="Le programme e-sport des 7 prochains jours : League of Legends, Valorant, Counter-Strike 2, Rocket League, Dota 2, Overwatch 2, Rainbow Six Siege. Mis à jour chaque jour.",
               none="Aucun match annoncé pour l'instant.", upcoming="Prochains matchs",
               upnone="Aucun match annoncé dans les 14 prochains jours.", tz="heure de Paris", updated="Mis à jour le",
               cta="Être prévenu avant chaque match", teams="equipes"),
    "en": dict(file="matches-this-week.html", news="whats-new.html", lang="en",
               days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
               months=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
               title="This week's matches", kicker="This week",
               lead="Matches of the top esports teams for the next 7 days, updated every morning. Paris time.",
               meta="The esports schedule for the next 7 days: League of Legends, Valorant, Counter-Strike 2, Rocket League, Dota 2, Overwatch 2, Rainbow Six Siege. Updated daily.",
               none="No match announced yet.", upcoming="Upcoming matches",
               upnone="No match announced in the next 14 days.", tz="Paris time", updated="Updated on",
               cta="Get alerted before every match", teams="teams"),
    "es": dict(file="partidos-de-la-semana.html", news="novedades.html", lang="es",
               days=["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
               months=["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
               title="Los partidos de la semana", kicker="Esta semana",
               lead="Los partidos de los grandes equipos de esports en los próximos 7 días, actualizados cada mañana. Hora de París.",
               meta="El calendario de esports de los próximos 7 días: League of Legends, Valorant, Counter-Strike 2, Rocket League, Dota 2, Overwatch 2, Rainbow Six Siege. Actualizado cada día.",
               none="Todavía no hay partidos anunciados.", tz="hora de París", updated="Actualizado el",
               cta="Recibe un aviso antes de cada partido", teams="teams"),
    "de": dict(file="spiele-der-woche.html", news="neuigkeiten.html", lang="de",
               days=["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
               months=["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
               title="Die Matches der Woche", kicker="Diese Woche",
               lead="Die Matches der großen Esport-Teams in den nächsten 7 Tagen, jeden Morgen aktualisiert. Pariser Zeit.",
               meta="Der Esport-Spielplan der nächsten 7 Tage: League of Legends, Valorant, Counter-Strike 2, Rocket League, Dota 2, Overwatch 2, Rainbow Six Siege. Täglich aktualisiert.",
               none="Noch keine Matches angekündigt.", tz="Pariser Zeit", updated="Aktualisiert am",
               cta="Vor jedem Match benachrichtigt werden", teams="teams"),
    "pt-BR": dict(file="partidas-da-semana.html", news="novidades.html", lang="pt-BR",
                  days=["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"],
                  months=["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
                  title="As partidas da semana", kicker="Esta semana",
                  lead="As partidas dos grandes times de esports nos próximos 7 dias, atualizadas toda manhã. Horário de Paris.",
                  meta="A agenda de esports dos próximos 7 dias: League of Legends, Valorant, Counter-Strike 2, Rocket League, Dota 2, Overwatch 2, Rainbow Six Siege. Atualizada todo dia.",
                  none="Nenhuma partida anunciada ainda.", tz="horário de Paris", updated="Atualizado em",
                  cta="Seja avisado antes de cada partida", teams="teams"),
}
HOME = {"fr": "./", "en": "en.html", "es": "es.html", "de": "de.html", "pt-BR": "pt.html"}
EXTRA = {
 "fr": {
  "results": "Résultats des 7 derniers jours",
  "reveal": "Voir le score",
  "res_none": "Aucun résultat cette semaine.",
  "spoil": "Les scores restent cachés : touche un match pour voir le sien.",
  "ev_title": "{e} : programme et résultats",
  "ev_lead": "Tous les matchs de {e} en heure de Paris, mis à jour chaque matin. Les scores restent cachés jusqu'à ce que tu les demandes.",
  "ev_up": "Prochains matchs",
  "ev_watch": "Comment regarder",
  "ev_watch_txt": "Les matchs sont diffusés en direct sur les chaînes officielles de l'organisateur, sur Twitch et YouTube. Dans eSportly, le direct s'affiche dans la fiche du match, seulement si tu le lances, et le score suit sur ton écran verrouillé.",
  "ev_cal": "Ajouter à mon calendrier",
  "ev_gcal": "Ajouter à Google Agenda",
  "events": "Grands événements",
  "ev_suffix": ""
 },
 "en": {
  "results": "Results from the last 7 days",
  "reveal": "Show the score",
  "res_none": "No results this week.",
  "spoil": "Scores stay hidden: tap a match to see its score.",
  "ev_title": "{e}: schedule and results",
  "ev_lead": "Every {e} match in Paris time, updated every morning. Scores stay hidden until you ask for them.",
  "ev_up": "Upcoming matches",
  "ev_watch": "How to watch",
  "ev_watch_txt": "Matches are streamed live on the organizer's official channels, on Twitch and YouTube. In eSportly, the stream shows on the match page, only if you start it, and the score follows on your Lock Screen.",
  "ev_cal": "Add to my calendar",
  "ev_gcal": "Add to Google Calendar",
  "events": "Big events",
  "ev_suffix": "-en"
 },
 "es": {
  "results": "Resultados de los últimos 7 días",
  "reveal": "Ver el marcador",
  "res_none": "Sin resultados esta semana.",
  "spoil": "Los marcadores quedan ocultos: toca un partido para ver el suyo.",
  "ev_title": "{e}: calendario y resultados",
  "ev_lead": "Todos los partidos de {e} en hora de París, actualizados cada mañana. Los marcadores quedan ocultos hasta que los pidas.",
  "ev_up": "Próximos partidos",
  "ev_watch": "Cómo verlo",
  "ev_watch_txt": "Los partidos se emiten en directo en los canales oficiales del organizador, en Twitch y YouTube. En eSportly, el directo aparece en la ficha del partido, solo si lo inicias, y el marcador sigue en tu pantalla bloqueada.",
  "ev_cal": "Añadir a mi calendario",
  "ev_gcal": "Añadir a Google Calendar",
  "events": "Grandes eventos",
  "ev_suffix": "-es"
 },
 "de": {
  "results": "Ergebnisse der letzten 7 Tage",
  "reveal": "Ergebnis zeigen",
  "res_none": "Diese Woche keine Ergebnisse.",
  "spoil": "Ergebnisse bleiben verborgen: Tippe auf ein Match, um sein Ergebnis zu sehen.",
  "ev_title": "{e}: Spielplan und Ergebnisse",
  "ev_lead": "Alle Matches von {e} in Pariser Zeit, jeden Morgen aktualisiert. Ergebnisse bleiben verborgen, bis du sie sehen willst.",
  "ev_up": "Nächste Matches",
  "ev_watch": "So schaust du zu",
  "ev_watch_txt": "Die Matches laufen live auf den offiziellen Kanälen des Veranstalters, auf Twitch und YouTube. In eSportly erscheint der Stream auf der Match-Seite, nur wenn du ihn startest, und das Ergebnis folgt auf deinem Sperrbildschirm.",
  "ev_cal": "Zu meinem Kalender hinzufügen",
  "ev_gcal": "Zu Google Kalender hinzufügen",
  "events": "Große Events",
  "ev_suffix": "-de"
 },
 "pt-BR": {
  "results": "Resultados dos últimos 7 dias",
  "reveal": "Ver o placar",
  "res_none": "Nenhum resultado nesta semana.",
  "spoil": "Os placares ficam escondidos: toque em uma partida para ver o dela.",
  "ev_title": "{e}: agenda e resultados",
  "ev_lead": "Todas as partidas de {e} no horário de Paris, atualizadas toda manhã. Os placares ficam escondidos até você pedir.",
  "ev_up": "Próximas partidas",
  "ev_watch": "Como assistir",
  "ev_watch_txt": "As partidas são transmitidas ao vivo nos canais oficiais do organizador, na Twitch e no YouTube. No eSportly, a transmissão aparece na página da partida, só se você iniciar, e o placar acompanha na tela bloqueada.",
  "ev_cal": "Adicionar ao meu calendário",
  "ev_gcal": "Adicionar ao Google Agenda",
  "events": "Grandes eventos",
  "ev_suffix": "-pt"
 }
}
EVENTS = {  # page → (nom, jeu) ; les matchs viennent de /calendrier/evenement/<page>.ics et /resultats/<page>.json
    "worlds-2026": ("Worlds 2026", "League of Legends"),
    "vct-champions-2026": ("VCT Champions 2026", "Valorant"),
    "esl-pro-league": ("ESL Pro League", "Counter-Strike 2"),
}
API = "https://lmavqchwevcvvneblqld.supabase.co/functions/v1/calendrier/"


def read_results(scope: str) -> list[dict]:
    try:
        with urllib.request.urlopen(f"{API}resultats/{scope}.json", timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        print(f"résultats {scope} : {error}")
        return []


def results_html(results: list[dict], t: dict, x: dict) -> str:
    """Résultats cachés par défaut (<details>, sans script) : on touche un match pour voir son score."""
    if not results:
        return f'<p>{x["res_none"]}</p>'
    items = []
    for r in results[:30]:
        moment = datetime.fromisoformat(r["date"].replace("Z", "+00:00")).astimezone(PARIS)
        day = f'{t["days"][moment.weekday()]} {moment.day} {t["months"][moment.month - 1]}'
        context = clean(" · ".join(v for v in (r.get("game"), r.get("league"), r.get("serie")) if v))
        score = " – ".join("?" if v is None else str(v) for v in r["score"])
        teams = " – ".join(r["teams"])
        items.append(f'<li><details><summary><b>{html.escape(teams)}</b><small>{html.escape(day)} · {html.escape(context)}</small>'
                     f'<span class="voir">{x["reveal"]}</span></summary><p class="score">{html.escape(r["teams"][0])} <b>{score}</b> {html.escape(r["teams"][1])}</p></details></li>')
    return f'<p class="maj">{x["spoil"]}</p><ul class="resultats">{"".join(items)}</ul>'



# Compétitions au nom d'un site de paris : on garde le match, mais on n'affiche que le jeu (règle « aucun pari »).
BETTING = re.compile(r"1win|stake|thunderpick|\bpari\b|parimatch|betboom|gg\.?bet|betway|bet365|rollbit|csgoempire|bc\.game", re.I)


def clean(description: str) -> str:
    if BETTING.search(description):
        return description.split(" · ")[0]
    return description


def unfold(text: str) -> list[str]:
    return text.replace("\r\n ", "").replace("\n ", "").splitlines()


def unescape_ics(value: str) -> str:
    return value.replace("\\n", " ").replace("\\,", ",").replace("\;", ";").replace("\\\\", "\\")


def read_calendar(slug: str, base: str = CAL) -> list[dict] | None:
    """None si le serveur n'a pas répondu (après un second essai) : la page garde alors son contenu d'hier."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(f"{base}{slug}.ics", timeout=60) as response:
                text = response.read().decode("utf-8")
            break
        except Exception as error:  # une équipe indisponible ne bloque pas les autres
            print(f"{slug} : {error}")
    else:
        return None
    events, current = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            if "DTSTART" in current and current.get("STATUS") != "CANCELLED":
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key.split(";")[0]] = clean(unescape_ics(value)) if key.startswith("DESCRIPTION") else unescape_ics(value)
    for event in events:
        event["start"] = datetime.strptime(event["DTSTART"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        event["end"] = datetime.strptime(event.get("DTEND", event["DTSTART"]), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return events


def when(event: dict, t: dict, with_day: bool = True) -> str:
    local = event["start"].astimezone(PARIS)
    hour = local.strftime("%H:%M")
    if not with_day:
        return hour
    return f'{t["days"][local.weekday()]} {local.day} {t["months"][local.month - 1]}, {hour}'


def json_ld(events: list[dict]) -> str:
    items = []
    for event in events:
        names = [n.strip() for n in event.get("SUMMARY", "").split("–")]
        item = {
            "@context": "https://schema.org", "@type": "SportsEvent", "name": event.get("SUMMARY", "Match"),
            "startDate": event["start"].isoformat(), "endDate": event["end"].isoformat(),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
            "location": {"@type": "VirtualLocation", "url": event.get("URL", URL)},
            "description": event.get("DESCRIPTION", ""), "url": event.get("URL", URL),
        }
        if len(names) == 2:
            item["competitor"] = [{"@type": "SportsTeam", "name": n} for n in names]
        items.append(item)
    return '<script type="application/ld+json">' + json.dumps(items, ensure_ascii=False) + "</script>"


def match_item(event: dict, t: dict, with_day: bool = True) -> str:
    link = html.escape(event.get("URL", URL))
    return (f'<li><a href="{link}" target="_top"><time datetime="{event["start"].isoformat()}">{html.escape(when(event, t, with_day))}</time>'
            f'<b>{html.escape(event.get("SUMMARY", "Match"))}</b><small>{html.escape(event.get("DESCRIPTION", ""))}</small></a></li>')


STYLE = (".matchs{list-style:none;padding:0;margin:0;display:grid;gap:10px}"
         ".matchs a{display:grid;gap:2px;padding:14px 18px;border-radius:18px;background:var(--surface);border:1px solid var(--border);color:var(--text);text-decoration:none}"
         ".matchs time{font-size:15px;color:var(--or);font-weight:700}.matchs b{font-size:18px}.matchs small{font-size:14px;color:var(--soft)}"
         ".jour{font:700 26px var(--display);margin:30px 0 12px}.maj{font-size:14px;color:var(--muted)}"
         ".resultats{list-style:none;padding:0;margin:0;display:grid;gap:10px}.resultats details{padding:14px 18px;border-radius:18px;background:var(--surface);border:1px solid var(--border)}"
         ".resultats summary{display:grid;gap:2px;cursor:pointer;list-style:none}.resultats summary::-webkit-details-marker{display:none}.resultats summary b{font-size:18px}"
         ".resultats small{font-size:14px;color:var(--soft)}.resultats .voir{font-size:14px;font-weight:700;color:var(--text);text-decoration:underline}"
         ".resultats details[open] .voir{display:none}.score{margin:10px 0 0;font-size:18px}.score b{font:700 26px var(--display);margin:0 8px}"
         ".evts{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}.evts a{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border-radius:999px;background:var(--surface);border:1px solid var(--border);color:var(--text);text-decoration:none;font-weight:600;font-size:15px}"
         ".cal-buttons{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.cal-google{display:inline-flex;align-items:center;min-height:54px;padding:0 24px;border-radius:999px;border:1px solid var(--border);color:var(--text);font-weight:700;text-decoration:none}")

WIDGET = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<meta name="robots" content="noindex"><meta name="referrer" content="strict-origin-when-cross-origin"><title>{name} – eSportly</title>
<style>:root{{color-scheme:light dark;--bg:#0A0E1A;--card:#141A2B;--border:#2C3550;--text:#F4F6FF;--soft:#C9CEDA;--or:#FFC53D;--accent:#FFC53D}}
@media (prefers-color-scheme:light){{:root{{--bg:#F6F7FB;--card:#FFFFFF;--border:#D5DAE6;--text:#0E1424;--soft:#3A4250;--accent:#6A4900}}}}
body{{margin:0;padding:12px;background:var(--bg);color:var(--text);font:15px/1.4 -apple-system,BlinkMacSystemFont,system-ui,sans-serif}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:8px}}a{{color:inherit;text-decoration:none}}
li a{{display:grid;gap:2px;padding:10px 12px;border-radius:12px;background:var(--card);border:1px solid var(--border)}}
time{{color:var(--accent);font-weight:700;font-size:13px}}b{{font-size:15px}}small{{color:var(--soft);font-size:12px}}
.f{{display:flex;justify-content:space-between;gap:8px;margin-top:10px;font-size:12px;color:var(--soft)}}.f a{{color:var(--accent);font-weight:700}}</style></head>
<body><ul>{items}</ul><p class="f"><span>{tz}</span><a href="{link}" target="_blank" rel="noopener">{follow} →</a></p></body></html>
"""

# 1) Pages d'équipes
organisations = sorted(p.stem for p in (SITE / "equipes").glob("*.html"))
everything: dict[str, dict] = {}
for slug in organisations:
    events = read_calendar(slug)
    if events is None:
        continue
    for event in events:
        everything[event.get("UID", event.get("URL"))] = event
    upcoming = sorted((e for e in events if NOW - timedelta(hours=3) <= e["start"] <= NOW + timedelta(days=14)),
                      key=lambda e: e["start"])[:5]
    for folder, code in (("equipes", "fr"), ("teams", "en")):
        page = SITE / folder / f"{slug}.html"
        if not page.exists():
            continue
        t = LANGS[code]
        source = page.read_text(encoding="utf-8")
        body = (f'<ul class="matchs">{"".join(match_item(e, t) for e in upcoming)}</ul><p class="maj">{t["tz"]}</p>{json_ld(upcoming)}'
                if upcoming else f'<p>{t["upnone"]}</p>')
        block = f'{START}\n<h2 id="prochains-matchs">{t["upcoming"]}</h2>\n{body}\n{END}'
        if START in source:
            source = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: block, source, flags=re.S)
        else:
            anchor = source.find("<!-- calendrier-equipe -->")
            if anchor < 0:
                anchor = source.find("</main>")
            source = source[:anchor] + block + "\n" + source[anchor:]
            source = source.replace("</style>", STYLE + "</style>", 1)
        page.write_text(source, encoding="utf-8")
    # Calendrier à intégrer sur un site de fans (iframe), une page par équipe et par langue, sans script.
    for code in ("fr", "en"):
        t = LANGS[code]
        team = SITE / ("equipes" if code == "fr" else "teams") / f"{slug}.html"
        if not team.exists():
            continue
        fiche = SITE / "equipes" / f"{slug}.json"
        name = json.loads(fiche.read_text(encoding="utf-8")).get("organisation", slug) if fiche.exists() else slug
        follow = (f"Suivre {name} avec eSportly" if code == "fr" else f"Follow {name} with eSportly")
        items = "".join(match_item(e, t) for e in upcoming[:3]) or f"<li><p>{t['upnone']}</p></li>"
        widget = SITE / "widget" / code / f"{slug}.html"
        widget.parent.mkdir(parents=True, exist_ok=True)
        widget.write_text(WIDGET.format(lang=code, name=html.escape(name), items=items, tz=t["tz"], follow=html.escape(follow),
                                        link=f"{URL}{'equipes' if code == 'fr' else 'teams'}/{slug}.html"), encoding="utf-8")

# 2) Les matchs de la semaine (5 langues)
week = sorted((e for e in everything.values() if NOW - timedelta(hours=3) <= e["start"] <= NOW + timedelta(days=7)),
              key=lambda e: e["start"])
names = {code: t["news"] for code, t in LANGS.items()}
week_results = read_results("semaine")
for code, t in LANGS.items():
    template = (SITE / t["news"]).read_text(encoding="utf-8")
    for other, news in names.items():  # liens de langue et hreflang : vers les pages de la semaine
        template = template.replace(news, LANGS[other]["file"])
    template = template.replace(LANGS[code]["file"].replace(".html", ".xml"), "")
    template = re.sub(r'<link rel="alternate" type="application/rss\+xml"[^>]*>\n?', "", template)
    template = re.sub(r"<title>.*?</title>", f"<title>{t['title']} – eSportly</title>", template, flags=re.S)
    template = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + t["meta"], template)
    template = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + t["title"] + " – eSportly", template)
    template = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + t["meta"], template)
    template = re.sub(r'(visite\?p=/)[a-z-]+', lambda m: m.group(1) + t["file"][:-5], template)
    template = re.sub(r'(<meta property="og:image" content=")[^"]*', lambda m: m.group(1) + f"{URL}partage/semaine-{code}.jpg", template)
    days, groups = [], {}
    for event in week:
        key = event["start"].astimezone(PARIS).date()
        groups.setdefault(key, []).append(event)
    content = []
    for day, events in groups.items():
        label = f'{t["days"][day.weekday()]} {day.day} {t["months"][day.month - 1]}'
        content.append(f'<h2 class="jour">{label[0].upper() + label[1:]}</h2><ul class="matchs">{"".join(match_item(e, t, False) for e in events)}</ul>')
    today = NOW.astimezone(PARIS)
    main = (f'<section class="hero"><span class="big" aria-hidden="true">eS</span><div class="kicker">{t["kicker"]}</div>'
            f'<h1>{t["title"]}</h1><p class="lead">{t["lead"]}</p>'
            f'<a class="cta" href="https://lmavqchwevcvvneblqld.supabase.co/functions/v1/visite?p=/{t["file"][:-5]}&amp;go=testflight">{t["cta"]}</a></section>'
            + f'<h2 class="jour">{EXTRA[code]["events"]}</h2><ul class="evts">'
            + "".join(f'<li><a href="{slug}{EXTRA[code]["ev_suffix"]}.html">{name}</a></li>' for slug, (name, _) in EVENTS.items()) + "</ul>"
            + ("".join(content) if content else f'<p>{t["none"]}</p>')
            + f'<h2 class="jour" id="resultats">{EXTRA[code]["results"]}</h2>' + results_html(week_results, t, EXTRA[code])
            + f'<p class="maj">{t["updated"]} {today.day} {t["months"][today.month - 1]} {today.year} · {t["tz"]}</p>'
            + json_ld(week[:60]))
    template = re.sub(r'<main class="wrap">.*?</main>', lambda _: f'<main class="wrap">{main}</main>', template, flags=re.S)
    if ".matchs{" not in template:
        template = template.replace("</style>", STYLE + "</style>", 1)
    (SITE / t["file"]).write_text(template, encoding="utf-8")
# 3) Grands événements (5 langues) : programme, résultats cachés, calendrier, comment regarder.
for slug, (event_name, game_name) in EVENTS.items():
    events = read_calendar(slug, API + "evenement/")
    if events is None:
        continue
    upcoming = sorted((e for e in events if e["start"] >= NOW - timedelta(hours=3)), key=lambda e: e["start"])[:60]
    results = read_results(slug)
    pages = {code: f"{slug}{EXTRA[code]['ev_suffix']}.html" for code in LANGS}
    for code, t in LANGS.items():
        x = EXTRA[code]
        template = (SITE / t["news"]).read_text(encoding="utf-8")
        for other, news in names.items():
            template = template.replace(news, pages[other])
        template = re.sub(r'<link rel="alternate" type="application/rss\+xml"[^>]*>\n?', "", template)
        title = x["ev_title"].format(e=event_name)
        lead = x["ev_lead"].format(e=event_name)
        template = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)} – eSportly</title>", template, flags=re.S)
        template = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + html.escape(lead), template)
        template = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + html.escape(title), template)
        template = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + html.escape(lead), template)
        template = re.sub(r'(visite\?p=/)[a-z-]+', lambda m: m.group(1) + pages[code][:-5], template)
        ics = f"lmavqchwevcvvneblqld.supabase.co/functions/v1/calendrier/evenement/{slug}.ics"
        gcal = "https://calendar.google.com/calendar/render?cid=" + quote("webcal://" + ics, safe="")
        groups = {}
        for event in upcoming:
            groups.setdefault(event["start"].astimezone(PARIS).date(), []).append(event)
        days = []
        for day, evs in groups.items():
            label = f'{t["days"][day.weekday()]} {day.day} {t["months"][day.month - 1]}'
            days.append(f'<h3 class="jour">{label[0].upper() + label[1:]}</h3><ul class="matchs">{"".join(match_item(e, t, False) for e in evs)}</ul>')
        today = NOW.astimezone(PARIS)
        main = (f'<section class="hero"><span class="big" aria-hidden="true">eS</span><div class="kicker">{html.escape(game_name)}</div>'
                f'<h1>{html.escape(title)}</h1><p class="lead">{html.escape(lead)}</p>'
                f'<a class="cta" href="https://lmavqchwevcvvneblqld.supabase.co/functions/v1/visite?p=/{pages[code][:-5]}&amp;go=testflight">{t["cta"]}</a></section>'
                f'<p class="cal-buttons"><a class="cta" href="webcal://{ics}">{x["ev_cal"]}</a><a class="cal-google" href="{gcal}" rel="noopener">{x["ev_gcal"]}</a></p>'
                f'<h2 class="jour">{x["ev_up"]}</h2>' + ("".join(days) if days else f'<p>{t["none"]}</p>')
                + f'<h2 class="jour" id="resultats">{x["results"]}</h2>' + results_html(results, t, x)
                + f'<h2 class="jour">{x["ev_watch"]}</h2><p>{x["ev_watch_txt"]}</p>'
                + f'<p class="maj">{t["updated"]} {today.day} {t["months"][today.month - 1]} {today.year} · {t["tz"]}</p>'
                + json_ld(upcoming))
        template = re.sub(r'<main class="wrap">.*?</main>', lambda _: f'<main class="wrap">{main}</main>', template, flags=re.S)
        template = re.sub(r'(<meta property="og:image" content=")[^"]*', lambda m: m.group(1) + f"{URL}partage/semaine-{code}.jpg", template)
        if ".resultats{" not in template:
            template = template.replace("</style>", STYLE + "</style>", 1)
        (SITE / pages[code]).write_text(template, encoding="utf-8")
    print(f"{event_name} : {len(upcoming)} à venir, {len(results)} résultats")

print(f"{len(organisations)} équipes, {len(week)} matchs cette semaine, {len(week_results)} résultats")
