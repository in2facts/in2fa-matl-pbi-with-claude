# Ultimate Formula 1 Dashboard

Advanced analytics and technical insights.
All in one dashboard.

_Spec carried over from the Claude personal project (uuid 01a03e8d-e6e9-74ef-af38-090eb35a909a, synced 2026-08-26T15:24:53.626Z)._

_Amended 2026-09-14: the original asked for a flag per race, a photo per
driver, and a car name and livery image per team. The API publishes none of
the four - no photo, image, flag, logo, livery, car, model or chassis field
exists anywhere in the data - so they are removed rather than left as
requirements nothing can satisfy. Country and nationality are published and
stay. Team colours are not published either, but they are carried in
build.py and become a column of the Team table, so anything team-coded still
works._

## Build brief

Build a self-contained HTML dashboard for the current F1 season with six sections, navigable via tabs or a sidebar:

- Schedule
- Results
- Driver Standings
- Constructor Standings
- Drivers
- Teams

Pull data from Jolpica API.

**Schedule**: all rounds for the season as cards or a table — round number, country, circuit, date range, and status (completed / upcoming / sprint weekend). Highlight the next race.

**Results**: a round-by-round table showing race winner, pole sitter, and (where applicable) sprint winner and sprint poleman for each Grand Prix, plus season stat highlights — most wins, most podiums, most poles, best average finish, largest and closest winning margins, biggest position gain. Include a driver points-by-round grid (driver rows, round columns, points or DNF/DNS/DSQ status per cell).

**Driver Standings**: ranked table — position, driver (with team), total points, and points gained since the previous round.

**Constructor Standings**: same structure at the team level — position, constructor, total points, gap to the round before.

**Drivers**: a card per driver with number, team, and season averages (e.g., qualifying/race pace rating or comparable metric).

**Teams**: a card per constructor with its livery colour, season totals, and current driver lineup.

Use each team's official color for anything team-coded (rows, bars, badges). Default to the most recent completed round. Make it a single HTML file with basic filtering by season/round, so I can open it locally and share it.
