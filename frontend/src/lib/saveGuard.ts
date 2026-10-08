// Bumped synchronously when the signed-in user is replaced. A heart request
// that fails afterwards must not write the previous account's saved ids back.
// Account deletion calls this from its own branch, before React re-renders.

let epoch = 0;

export function currentSaveEpoch(): number {
  return epoch;
}

export function bumpSaveEpoch(): void {
  epoch += 1;
}
