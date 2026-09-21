import Accordion from "@/components/ui/accordion";

export const FAQ_ITEMS = [
  {
    id: "booking-changes",
    question: "Can I change or cancel my booking?",
    answer:
      "Yes. You can cancel any pending or confirmed booking from your My Bookings page. Cancellations are confirmed with a prompt before they go through, and eligible refunds are processed automatically.",
  },
  {
    id: "seat-selection",
    question: "How do I choose my seat?",
    answer:
      "After booking, you can pick your seat on the booking flow. Available seats are shown in real time and are held while you select them, so two people can't book the same seat.",
  },
  {
    id: "payment-methods",
    question: "What payment methods do you accept?",
    answer:
      "We accept credit and debit cards, UPI, net banking and popular wallets. All payments are processed securely through our payment provider.",
  },
  {
    id: "ticket-delivery",
    question: "When do I receive my ticket?",
    answer:
      "Tickets are issued the moment your payment is confirmed. You'll get an email and SMS with your PNR and booking reference instantly.",
  },
  {
    id: "check-in",
    question: "How do I check in for my flight?",
    answer:
      "Use your PNR (6-character reference) to check in online 24 hours before departure. Your booking details include everything you need.",
  },
  {
    id: "baggage",
    question: "What's the baggage allowance?",
    answer:
      "Baggage depends on your airline and fare class. Head to the flight details page for your route to see the exact allowance before you book.",
  },
];

export default function FaqSection() {
  return (
    <section
      id="faq"
      aria-labelledby="faq-heading"
      className="mx-auto max-w-3xl scroll-mt-20 px-4 py-20"
    >
      <div className="mb-10 text-center">
        <h2
          id="faq-heading"
          className="mb-3 text-3xl font-bold tracking-tight"
        >
          Frequently asked questions
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400">
          Answers to the questions we hear the most.
        </p>
      </div>
      <Accordion items={FAQ_ITEMS} defaultOpen="booking-changes" />
    </section>
  );
}