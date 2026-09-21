import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import Header from "@/components/layout/header";
import Footer from "@/components/layout/footer";
import SkipLink from "@/components/layout/skip-link";
import ScrollProgress from "@/components/layout/scroll-progress";
import ScrollToTop from "@/components/layout/scroll-to-top";
import FloatingContact from "@/components/layout/floating-contact";
import CookieBanner from "@/components/layout/cookie-banner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Fast - Flight Booking",
  description: "Search, book and manage flights",
};

const themeInitScript = `(function(){try{var t=localStorage.getItem('theme');if(t==='light'||t==='dark'){document.documentElement.classList.toggle('dark',t==='dark')}else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches){document.documentElement.classList.add('dark')}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="flex min-h-full flex-col bg-zinc-50 dark:bg-zinc-950" suppressHydrationWarning>
        <ThemeProvider>
          <AuthProvider>
            <SkipLink />
            <ScrollProgress />
            <Header />
            <main id="main-content" className="flex-1 scroll-mt-20" tabIndex={-1}>
              {children}
            </main>
            <FloatingContact href="mailto:support@fast.example" />
            <Footer />
            <ScrollToTop />
            <CookieBanner />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}