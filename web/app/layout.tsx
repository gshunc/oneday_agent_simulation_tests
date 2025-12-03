import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OneDay Test Runner",
  description: "Run OneDay agent simulation tests",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{
        fontFamily: 'system-ui, -apple-system, sans-serif',
        margin: 0,
        padding: '2rem',
        backgroundColor: '#f5f5f5',
        minHeight: '100vh'
      }}>
        {children}
      </body>
    </html>
  );
}
