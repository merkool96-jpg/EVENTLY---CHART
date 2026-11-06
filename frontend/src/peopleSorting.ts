export type PeopleSortKey =
  | "name"
  | "visits"
  | "registrations"
  | "value"
  | "last_seen";
export type PeopleSort = { key: PeopleSortKey; direction: "asc" | "desc" };
export const defaultPeopleSort: PeopleSort = {
  key: "visits",
  direction: "desc",
};
export const sortLabels: Record<PeopleSortKey, string> = {
  name: "Partecipante",
  visits: "Presenze",
  registrations: "Registrazioni",
  value: "Valore attribuito",
  last_seen: "Ultimo incontro",
};
type SortablePerson = {
  id: number;
  name: string;
  visits: number;
  registrations: number;
  value: number;
  last_seen: string | null;
};
const alphabet = new Intl.Collator("it", {
  sensitivity: "base",
  numeric: true,
});

export function nextPeopleSort(
  current: PeopleSort,
  key: PeopleSortKey,
): PeopleSort {
  return {
    key,
    direction:
      current.key === key
        ? current.direction === "asc"
          ? "desc"
          : "asc"
        : key === "name"
          ? "asc"
          : "desc",
  };
}

export function sortPeople<T extends SortablePerson>(
  people: readonly T[],
  sort: PeopleSort,
): T[] {
  return [...people].sort((a, b) => {
    let comparison = 0;
    if (sort.key === "last_seen") {
      // Missing dates always come last, also when the oldest date is first.
      if (!a.last_seen && b.last_seen) return 1;
      if (a.last_seen && !b.last_seen) return -1;
      comparison = (a.last_seen || "").localeCompare(b.last_seen || "");
    } else if (sort.key === "name") {
      comparison = alphabet.compare(a.name, b.name);
    } else {
      comparison = a[sort.key] - b[sort.key];
    }
    if (comparison) return sort.direction === "asc" ? comparison : -comparison;
    // Stable, explicit tie-breaks preserve the official attendance ranking.
    return (
      b.visits - a.visits ||
      (b.last_seen || "").localeCompare(a.last_seen || "") ||
      alphabet.compare(a.name, b.name) ||
      a.id - b.id
    );
  });
}
