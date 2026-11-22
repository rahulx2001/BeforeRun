// Inert annotation-only fixture: a declared compatibility check, not a behavior verdict.
const supportedMajor = 22;
const currentMajor = Number(process.versions.node.split(".")[0]);
if (currentMajor < supportedMajor) {
  console.log("Fixture annotation only: Node 22 or newer is requested.");
}
