/**
 * Tests for World Cup Fan App
 */
const { getMatchSchedule, getVenueInfo, getGroupStandings, VENUES } = require('../src/app');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✅ PASS: ${message}`);
    passed++;
  } else {
    console.log(`  ❌ FAIL: ${message}`);
    failed++;
  }
}

console.log("\n🧪 Running World Cup Fan App Tests\n");

// Test venue lookup
console.log("📋 Venue Tests:");
const venue = getVenueInfo(1);
assert(venue.name === "MetLife Stadium", "MetLife Stadium found by ID");
assert(venue.country === "USA", "MetLife is in USA");

const badVenue = getVenueInfo(999);
assert(badVenue.error === "Venue not found", "Invalid venue returns error");

// Test match schedule
console.log("\n📋 Schedule Tests:");
const schedule = getMatchSchedule(1);
assert(schedule.venue === "MetLife Stadium", "Schedule returns correct venue name");
assert(schedule.matches.length === 3, "Schedule has 3 matches");

// Test group standings
console.log("\n📋 Group Tests:");
const groupA = getGroupStandings("A");
assert(groupA.length === 4, "Group A has 4 teams");
assert(groupA[0].points === 0, "Initial points are 0");

const badGroup = getGroupStandings("Z");
assert(badGroup.error === "Invalid group", "Invalid group returns error");

// Test all venues exist
console.log("\n📋 Data Integrity:");
assert(VENUES.length === 8, "All 8 venues loaded");

console.log(`\n${"=".repeat(40)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log(`${"=".repeat(40)}\n`);

if (failed > 0) process.exit(1);
