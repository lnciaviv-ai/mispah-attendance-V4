# Neon (gratis permanente data) + Render

## Hoekom
Render se gratis skyf is tydelik. Neon is ’n **gratis Postgres-databasis** in die wolk —
jou leerdersdata bly daar, selfs as Render slaap.

## Stap 1 – Skep Neon-databasis
1. Gaan na https://neon.tech
2. Teken in met GitHub / Google / e-pos
3. **Create a project**
   - Naam: `mispah-attendance`
   - Region: kies iets naby (bv. Europe)
4. As die projek oop is, gaan na **Connection details** / **Dashboard**
5. Kopieer die **Connection string** (begin met `postgresql://` of `postgres://`)
   - Dit lyk soos: `postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`

## Stap 2 – Sit dit op Render
1. https://dashboard.render.com → jou diens (`mispah-attendance-v4`)
2. **Environment** → **Add Environment Variable**
   - Key: `DATABASE_URL`
   - Value: *plak die Neon connection string*
3. Save

## Stap 3 – Dateer die kode op
1. Laai die nuwe zip op GitHub (`db.py`, `server.py`, `requirements.txt`)
2. Render → **Manual Deploy → Deploy latest commit**
3. In die logs moet jy sien: `Database initialised: PostgreSQL (Neon)`

## Stap 4 – Toets
1. Open jou webwerf
2. Teken in: `admin` / `admin123`
3. Voeg ’n toets-leerder by
4. Wag 20 minute (of Manual Deploy weer)
5. Die leerder moet **nog daar wees**

## Belangrik
- Sodra `DATABASE_URL` gesit is, word **nie meer** die ou SQLite-lêer gebruik nie
- Eerste keer is die databasis leeg behalwe demo-klasse/onderwysers — voeg jou regte leerders weer by (of herstel vanaf JSON-rugsteun onder Instellings)
- Moenie die Neon connection string publiek deel nie (dit bevat ’n wagwoord)

## As iets verkeerd is
- Log sê "No module named psycopg2" → requirements.txt is nie op GitHub nie, of build het misluk
- "connection refused" → verkeerde DATABASE_URL of Neon projek is geskors
- Data lyk leeg → normale eerste begin op Neon; voeg leerders by of herstel rugsteun
