/**
 * World Cup 2026 — Stadium Operations Dashboard
 * Tracks gate occupancy, security checkpoint status, and venue capacity.
 */

const STADIUMS = [
  { id: 1, name: "MetLife Stadium", capacity: 82500, gates: 12 },
  { id: 2, name: "AT&T Stadium", capacity: 80000, gates: 14 },
  { id: 3, name: "SoFi Stadium", capacity: 70240, gates: 10 },
  { id: 4, name: "Hard Rock Stadium", capacity: 64767, gates: 9 },
  { id: 5, name: "Lumen Field", capacity: 68740, gates: 8 },
  { id: 6, name: "Estadio Azteca", capacity: 87523, gates: 16 },
  { id: 7, name: "BMO Field", capacity: 30000, gates: 6 },
  { id: 8, name: "BC Place", capacity: 54500, gates: 8 },
];

function getStadium(id) {
  const stadium = STADIUMS.find(s => s.id === id);
  if (!stadium) return { error: "Stadium not found" };
  return stadium;
}

function getGateStatus(stadiumId, occupancy) {
  const stadium = getStadium(stadiumId);
  if (stadium.error) return stadium;

  const pctFull = occupancy / stadium.capacity;
  let status = "open";
  if (pctFull >= 1) status = "at_capacity";
  else if (pctFull >= 0.9) status = "near_capacity";

  return {
    stadium: stadium.name,
    occupancy,
    capacity: stadium.capacity,
    percent_full: Math.round(pctFull * 100),
    status,
    gates_open: stadium.gates,
  };
}

function totalCapacity() {
  return STADIUMS.reduce((sum, s) => sum + s.capacity, 0);
}

module.exports = { STADIUMS, getStadium, getGateStatus, totalCapacity };
