# Life Dashboard

A personal web app that brings diet tracking, expense tracking, daily
habit stats, and university management into a single dashboard and a
single local database.

Built as a personal project to replace several separate apps I used to
track my daily life — with the explicit goal of being something I would
actually open and use every day, not a technical showcase.

## Features

- **Dashboard** — a single home page summarizing today: calories,
  protein, weight, sleep, study hours, gym, plus a money summary and
  14-day trend charts.
- **Diet** — log food per meal (breakfast/lunch/dinner/snack); daily
  totals for calories, protein, carbs, and fats are calculated
  automatically against configurable targets.
- **Weight** — track body weight over time with a trend chart.
- **Money** — track both expenses and income, categorized, with daily/
  weekly/monthly totals and a net balance (income − expenses).
- **Life Stats** — daily habit tracking: sleep, study, reading, water,
  gym, steps, mood, with 30-day trend charts.
- **University** — an exam logbook (grades, credits/CFU), a weekly class
  schedule, and a GPA/graduation-grade calculator (Italian university
  system: weighted average by credits, projected final grade out of 110).
- **History** — a unified view of the most recent entries across every
  category.
- **Settings** — configurable nutrition targets and currency.

## Tech stack

- **Backend:** Python, Flask
- **Database:** SQLite (single file, zero external setup)
- **Frontend:** HTML, CSS, vanilla JavaScript (no frontend framework)
- **Charts:** Chart.js, bundled locally as a static file (no CDN
  dependency — the app works fully offline)

The stack was chosen deliberately to stay simple: no ORM, no frontend
framework, no Docker — direct SQL queries and small, readable Flask
routes. The goal was to keep every part of the app easy to explain and
reason about.

## Project structure

```
life-dashboard/
├── app.py                  # Flask application: all routes
├── database.py              # SQLite connection + schema initialization
├── requirements.txt
├── README.md
│
├── templates/               # Jinja2 templates
│   ├── base.html              # Shared layout + navigation
│   ├── dashboard.html         # Home: today's summary + charts
│   ├── diet.html
│   ├── weight.html
│   ├── money.html
│   ├── life_stats.html
│   ├── university.html         # Exam logbook, schedule, GPA calculator
│   ├── history.html
│   └── settings.html
│
├── static/
│   ├── css/style.css          # Design system (CSS variables for theming)
│   └── js/
│       ├── app.js               # Mobile nav toggle
│       └── chart.umd.js          # Chart.js, bundled locally
│
└── data/                     # SQLite database is created here automatically
```

## Getting started

Requires Python 3.9+.

```bash
git clone https://github.com/<your-username>/life-dashboard.git
cd life-dashboard
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser. The SQLite database is
created automatically on first run — no setup step needed.

## Database schema

| Table | Purpose |
|---|---|
| `food_entries` | Logged food items (meal, macros, date) |
| `weight_entries` | One body weight entry per day |
| `expenses` | Expenses and income (categorized, with type) |
| `daily_stats` | One row per day: sleep, study, reading, water, gym, steps, mood |
| `exams` | Exam logbook: passed exams (with grade) or planned (with date) |
| `class_schedule` | Recurring weekly class schedule |
| `university_settings` | GPA target, total credits required, thesis/bonus points |
| `settings` | Nutrition targets and currency |

All tables are created automatically on first run via
`CREATE TABLE IF NOT EXISTS`.

## Design notes

- **No authentication** — this is a local, single-user personal app by design.
- **One weight/stats entry per day** — re-submitting the same date updates
  the existing entry instead of duplicating it (`INSERT ... ON CONFLICT
  DO UPDATE`).
- **GPA and graduation-grade projection only shown when meaningful** — the
  app won't show a misleading "gap to target GPA" if you haven't logged
  any exams yet, even if a target average is set.
- **Local-first** — no cloud sync, all data stays in a local SQLite file.

## License

MIT — feel free to fork and adapt for your own use.
