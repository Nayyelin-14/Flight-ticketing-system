export interface Airport {
  code: string;
  name: string;
}

export const AIRPORTS: Airport[] = [
  { code: "DEL", name: "Delhi" },
  { code: "BOM", name: "Mumbai" },
  { code: "BLR", name: "Bangalore" },
  { code: "MAA", name: "Chennai" },
  { code: "CCU", name: "Kolkata" },
  { code: "HYD", name: "Hyderabad" },
  { code: "GOI", name: "Goa" },
  { code: "PNQ", name: "Pune" },
];

export function airportLabel(code: string): string {
  const airport = AIRPORTS.find((a) => a.code === code);
  return airport ? `${airport.name} (${airport.code})` : code;
}