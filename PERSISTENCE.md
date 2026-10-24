# Hoekom verdwyn data op Render? + Hoe om dit permanent te maak

## Oorsaak
Render se **gratis** webdiens gebruik ’n tydelike hardeskyf. Wanneer die diens:
- slaap (na ~15 minute sonder besoekers), of
- herontplooi word,

word **alle lêers uitgevee** — insluitend die SQLite-databasis. Daarom verdwyn leerders wat jy bygevoeg het.

## Oplossing A (aanbeveel): Persistent Disk op Render

1. Gaan na jou diens op https://dashboard.render.com
2. **Settings** → **Disks** → **Add disk**
3. Mount path: `/data`
4. Size: 1 GB is genoeg
5. **Environment** → Add:
   - Key: `ATTENDANCE_DB`
   - Value: `/data/attendance.db`
6. **Manual Deploy** sodat dit herbegin

> Let wel: Persistent disks vereis gewoonlik ’n betaalde instance (Starter). Dit is die betroubaarste opsie.

## Oplossing B (gratis tydelik): Rugsteun gereeld

1. Teken in as admin
2. **Instellings** → **Laai volle rugsteun af**
3. Stoor die JSON-lêer op jou rekenaar / Google Drive
4. As data verdwyn: **Instellings** → kies die lêer → **Herstel data**

Doen dit elke keer nadat jy baie leerders bygevoeg het.

## Oplossing C: Ander gasheer met permanente skyf
Railway, Fly.io of ’n skool-rekenaar hou SQLite permanent sonder ekstra koste.
