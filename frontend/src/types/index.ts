export interface Flight {
  id: string;
  airline_id: string;
  airline_name: string;
  airline_code: string;
  origin: string;
  destination: string;
  dep_time: string;
  arrival_time: string;
  total_seats: number;
  status: "scheduled" | "delayed" | "cancelled" | "completed";
  price: number;
}

export interface Seat {
  id: string;
  flight_id: string;
  seat_number: string;
  class: "economy" | "business" | "first";
  status: "available" | "reserved" | "booked";
  price: number;
}

export interface Booking {
  id: string;
  user_id: string;
  flight_id: string;
  flight?: Flight;
  seat_number: string;
  status: "pending" | "confirmed" | "cancelled" | "completed";
  price: number;
  payment_id?: string;
  payment?: Payment;
  booking_date: string;
}

export interface Payment {
  id: string;
  booking_id: string;
  amount: number;
  method: "credit_card" | "debit_card" | "upi" | "net_banking" | "wallet";
  status: "pending" | "completed" | "failed" | "refunded";
  transaction_id?: string;
  paid_at?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  phone: string;
}

export interface SearchParams {
  origin: string;
  destination: string;
  date: string;
  passengers: number;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
