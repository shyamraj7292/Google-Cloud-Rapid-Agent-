/**
 * Tests for World Cup Stadium Dashboard
 */
const { getStadium, getGateStatus, totalCapacity, STADIUMS } = require('../src/app');

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

console.log("\n🧪 Running Stadium Dashboard Tests\n");

console.log("📋 Stadium Lookup Tests:");
const stadium = getStadium(1);
assert(stadium.name === "MetLife Stadium", "MetLife Stadium found by ID");
assert(stadium.capacity === 82500, "MetLife capacity is correct");

const badStadium = getStadium(999);
assert(badStadium.error === "Stadium not found", "Invalid stadium returns error");

console.log("\n📋 Gate Status Tests:");
const status = getGateStatus(1, 50000);
assert(status.status === "open", "Gate status is open below 90% capacity");

const nearFull = getGateStatus(1, 75000);
assert(nearFull.status === "near_capacity", "Gate status is near_capacity above 90%");

const full = getGateStatus(1, 82500);
assert(full.status === "at_capacity", "Gate status is at_capacity at 100%");

console.log("\n📋 Data Integrity:");
assert(STADIUMS.length === 8, "All 8 stadiums loaded");
assert(totalCapacity() > 0, "Total capacity is positive");

console.log(`\n${"=".repeat(40)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log(`${"=".repeat(40)}\n`);

if (failed > 0) process.exit(1);
