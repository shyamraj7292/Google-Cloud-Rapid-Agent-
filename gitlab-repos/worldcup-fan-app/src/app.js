/**
 * World Cup 2026 Fan App — Core Application Module
 * Provides match schedules, scores, and venue information
 */

const VENUES = [
  { id: 1, name: "MetLife Stadium", city: "East Rutherford, NJ", country: "USA", capacity: 82500 },
  { id: 2, name: "AT&T Stadium", city: "Arlington, TX", country: "USA", capacity: 80000 },
  { id: 3, name: "SoFi Stadium", city: "Inglewood, CA", country: "USA", capacity: 70240 },
  { id: 4, name: "Hard Rock Stadium", city: "Miami Gardens, FL", country: "USA", capacity: 64767 },
  { id: 5, name: "Lumen Field", city: "Seattle, WA", country: "USA", capacity: 68740 },
  { id: 6, name: "Estadio Azteca", city: "Mexico City", country: "Mexico", capacity: 87523 },
  { id: 7, name: "BMO Field", city: "Toronto, ON", country: "Canada", capacity: 30000 },
  { id: 8, name: "BC Place", city: "Vancouver, BC", country: "Canada", capacity: 54500 },
];

const GROUPS = {
  A: ["Qatar", "Ecuador", "Senegal", "Netherlands"],
  B: ["England", "Iran", "USA", "Wales"],
  C: ["Argentina", "Saudi Arabia", "Mexico", "Poland"],
  D: ["France", "Australia", "Denmark", "Tunisia"],
  E: ["Spain", "Costa Rica", "Germany", "Japan"],
  F: ["Belgium", "Canada", "Morocco", "Croatia"],
  G: ["Brazil", "Serbia", "Switzerland", "Cameroon"],
  H: ["Portugal", "Ghana", "Uruguay", "South Korea"],
};

function getMatchSchedule(venueId) {
  const venue = VENUES.find(v => v.id === venueId);
  if (!venue) return { error: "Venue not found" };
  
  return {
    venue: venue.name,
    city: venue.city,
    matches: [
      { round: "Group Stage", date: "2026-06-11", teams: "TBD vs TBD", time: "18:00 ET" },
      { round: "Group Stage", date: "2026-06-15", teams: "TBD vs TBD", time: "15:00 ET" },
      { round: "Round of 32", date: "2026-07-01", teams: "TBD vs TBD", time: "20:00 ET" },
    ]
  };
}

function getVenueInfo(venueId) {
  const venue = VENUES.find(v => v.id === venueId);
  if (!venue) return { error: "Venue not found" };
  return venue;
}

function getGroupStandings(group) {
  const teams = GROUPS[group.toUpperCase()];
  if (!teams) return { error: "Invalid group" };
  
  return teams.map((team, i) => ({
    position: i + 1,
    team,
    played: 0,
    won: 0,
    drawn: 0,
    lost: 0,
    gd: 0,
    points: 0,
  }));
}

module.exports = { getMatchSchedule, getVenueInfo, getGroupStandings, VENUES, GROUPS };
