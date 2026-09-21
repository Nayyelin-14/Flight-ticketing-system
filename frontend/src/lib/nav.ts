export interface NavLink {
  label: string;
  href: string;
}

export const PUBLIC_LINKS: NavLink[] = [
  { label: "Flights", href: "/flights" },
  { label: "Help", href: "/#faq" },
];

export const AUTH_LINKS: NavLink[] = [
  { label: "My Bookings", href: "/bookings" },
];

export const SEARCHABLE_PAGES: NavLink[] = [
  { label: "Home", href: "/" },
  { label: "Search Flights", href: "/flights" },
  { label: "My Bookings", href: "/bookings" },
  { label: "Login", href: "/login" },
  { label: "Create Account", href: "/register" },
  { label: "Flight Help & FAQ", href: "/#faq" },
];