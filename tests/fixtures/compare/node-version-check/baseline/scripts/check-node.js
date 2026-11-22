// Inert fixture: print a compatibility message; do not use as a malware example.
const requiredMajor = 20;
const actualMajor = Number(process.versions.node.split(".")[0]);
if (actualMajor !== requiredMajor) {
  console.log(`This fictional demo expects Node ${requiredMajor}.`);
} else {
  console.log("The fictional runtime check passed.");
}
