#!/bin/bash
# Mide cuánta CPU gasta la mascota, y cuánta le hace gastar al compositor.
#
# Lee /proc directamente (utime + stime del proceso) en vez de fiarse del %CPU
# de `top`, que es una media que arrastra historia: aquí interesa el gasto de
# ESTA ventana de tiempo, no el de toda la vida del proceso.
#
# Se corre DOS veces y se comparan: una con la mascota en el escritorio y otra
# sin ella (menú del clic derecho → «Ocultar del escritorio»). La diferencia en
# el compositor es el coste que la mascota provoca fuera de su propio proceso,
# y que por eso no sale en ninguna otra medición.
#
#   ./medir-cpu.sh          # 60 s
#   ./medir-cpu.sh 120      # o los segundos que quieras
set -uo pipefail

SEGUNDOS=${1:-60}
CLK=$(getconf CLK_TCK)

jiffies() { awk '{print $14+$15}' "/proc/$1/stat" 2>/dev/null; }

pid_mascota=$(pgrep -f "python3 -m claudepet" | head -1)
pid_shell=$(pgrep -x gnome-shell | head -1)
[ -z "$pid_shell" ] && pid_shell=$(pgrep -x kwin_wayland | head -1)

if [ -z "$pid_mascota" ]; then
  echo "No encuentro el proceso de Claude Pet. ¿Está corriendo?  (claudepet &)"
  exit 1
fi

declare -A antes
for p in $pid_mascota $pid_shell; do antes[$p]=$(jiffies "$p"); done

echo "Midiendo ${SEGUNDOS}s… (no toques la mascota mientras tanto)"
sleep "$SEGUNDOS"

printf "\n%-24s %8s\n" "proceso" "CPU"
for par in "claudepet:$pid_mascota" "compositor:$pid_shell"; do
  nombre=${par%%:*}; p=${par##*:}
  [ -z "$p" ] && { printf "%-24s %8s\n" "$nombre" "n/d"; continue; }
  d=$(( $(jiffies "$p") - ${antes[$p]} ))
  awk -v d="$d" -v clk="$CLK" -v s="$SEGUNDOS" -v n="$nombre" \
      'BEGIN{ printf "%-24s %7.2f %%\n", n, d/clk/s*100 }'
done

echo
echo "Ahora repítelo con la mascota oculta y compara el compositor."
