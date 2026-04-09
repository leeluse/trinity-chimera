export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0e14] text-white">
      {children}
    </div>
  );
}