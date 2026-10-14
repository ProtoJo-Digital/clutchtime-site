# Mise à jour quotidienne du site (GitHub Actions, voir .github/workflows/matchs.yml), sans aucun appel à
# PandaScore : les matchs viennent des calendriers publics du serveur d'eSportly (cache du relais).
# 1) « Prochains matchs » sur chaque page d'équipe (fr et en), avec les données « événement sportif » pour Google.
# 2) Les pages « Les matchs de la semaine » dans les 5 langues, fabriquées à partir des pages « Nouveautés ».
# Usage : python3 .github/scripts/matchs.py   (depuis la racine du site)
import html
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
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


def unfold(text: str) -> list[str]:
    return text.replace("\r\n ", "").replace("\n ", "").splitlines()


def unescape_ics(value: str) -> str:
    return value.replace("\\n", " ").replace("\\,", ",").replace("\;", ";").replace("\\\\", "\\")


def read_calendar(slug: str) -> list[dict]:
    try:
        with urllib.request.urlopen(f"{CAL}{slug}.ics", timeout=30) as response:
            text = response.read().decode("utf-8")
    except Exception as error:  # une équipe indisponible ne bloque pas les autres
        print(f"{slug} : {error}")
        return []
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
            current[key.split(";")[0]] = unescape_ics(value)
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
    return (f'<li><a href="{link}"><time datetime="{event["start"].isoformat()}">{html.escape(when(event, t, with_day))}</time>'
            f'<b>{html.escape(event.get("SUMMARY", "Match"))}</b><small>{html.escape(event.get("DESCRIPTION", ""))}</small></a></li>')


STYLE = (".matchs{list-style:none;padding:0;margin:0;display:grid;gap:10px}"
         ".matchs a{display:grid;gap:2px;padding:14px 18px;border-radius:18px;background:var(--surface);border:1px solid var(--border);color:var(--text);text-decoration:none}"
         ".matchs time{font-size:15px;color:var(--or);font-weight:700}.matchs b{font-size:18px}.matchs small{font-size:14px;color:var(--soft)}"
         ".jour{font:700 26px var(--display);margin:30px 0 12px}.maj{font-size:14px;color:var(--muted)}")

# 1) Pages d'équipes
organisations = sorted(p.stem for p in (SITE / "equipes").glob("*.html"))
everything: dict[str, dict] = {}
for slug in organisations:
    events = read_calendar(slug)
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

# 2) Les matchs de la semaine (5 langues)
week = sorted((e for e in everything.values() if NOW - timedelta(hours=3) <= e["start"] <= NOW + timedelta(days=7)),
              key=lambda e: e["start"])
names = {code: t["news"] for code, t in LANGS.items()}
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
            f'<a class="cta" href="https://testflight.apple.com/join/MSEj61gQ">{t["cta"]}</a></section>'
            + ("".join(content) if content else f'<p>{t["none"]}</p>')
            + f'<p class="maj">{t["updated"]} {today.day} {t["months"][today.month - 1]} {today.year} · {t["tz"]}</p>'
            + json_ld(week[:60]))
    template = re.sub(r'<main class="wrap">.*?</main>', lambda _: f'<main class="wrap">{main}</main>', template, flags=re.S)
    if ".matchs{" not in template:
        template = template.replace("</style>", STYLE + "</style>", 1)
    (SITE / t["file"]).write_text(template, encoding="utf-8")
print(f"{len(organisations)} équipes, {len(week)} matchs cette semaine")
