# [Frontend Real-time Integration v2] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock data in the existing dashboard with Supabase real-time subscriptions and integrate Monaco Editor for code viewing.

**Architecture:** Keep the existing UI structure intact while replacing data sources with Supabase real-time subscriptions and upgrading the code viewer component.

**Tech Stack:** Next.js, Supabase JavaScript Client, Monaco Editor, Chart.js

---

### Task 1: Supabase Client Setup & Environment Configuration
**Files:**
- Create: `front/lib/supabase.ts`
- Modify: `front/.env.local`

- [ ] **Step 1: Create Supabase client configuration**
```typescript
// front/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```
- [ ] **Step 2: Add environment variables to .env.local**
```bash
# front/.env.local
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```
- [ ] **Step 3: Commit**
```bash
git add front/lib/supabase.ts front/.env.local
git commit -m "feat: add Supabase client configuration"
```

### Task 2: Real-time Agent Performance Subscription ✅ COMPLETED
**Files:**
- Modify: `front/app/ba/v2/page.tsx`

- [x] **Step 1: Remove mock metrics and add Supabase subscription**
```typescript
// Remove lines 13-81 (mock metrics)
// Add real-time subscription logic
useEffect(() => {
  const subscription = supabase
    .channel('agent-performance')
    .on('postgres_changes', 
      { event: 'INSERT', schema: 'public', table: 'backtest_results' },
      (payload) => {
        // Update agent performance state
        setAgentPerformance(prev => updatePerformance(prev, payload.new))
      }
    )
    .subscribe()

  return () => {
    subscription.unsubscribe()
  }
}, [])
```
- [x] **Step 2: Implement updatePerformance helper function**
```typescript
const updatePerformance = (current: any[], newResult: any) => {
  // Logic to update performance data with new backtest result
}
```
- [x] **Step 3: Commit**
```bash
git add front/app/ba/v2/page.tsx
git commit -m "feat: replace mock metrics with Supabase real-time subscription"
```

### Task 3: Strategy Code Real-time Updates
**Files:**
- Modify: `front/app/ba/v2/page.tsx`

- [ ] **Step 1: Add strategies table subscription**
```typescript
useEffect(() => {
  const subscription = supabase
    .channel('strategy-updates')
    .on('postgres_changes', 
      { event: 'INSERT', schema: 'public', table: 'strategies' },
      (payload) => {
        // Update strategy code display
        setLatestStrategy(payload.new)
      }
    )
    .subscribe()

  return () => {
    subscription.unsubscribe()
  }
}, [])
```
- [ ] **Step 2: Add agent status subscription**
```typescript
useEffect(() => {
  const subscription = supabase
    .channel('agent-status')
    .on('postgres_changes', 
      { event: 'UPDATE', schema: 'public', table: 'agents' },
      (payload) => {
        // Update agent status indicators
        setAgentStatus(prev => updateStatus(prev, payload.new))
      }
    )
    .subscribe()

  return () => {
    subscription.unsubscribe()
  }
}, [])
```
- [ ] **Step 3: Commit**
```bash
git add front/app/ba/v2/page.tsx
git commit -m "feat: add real-time strategy and agent status updates"
```

### Task 4: Monaco Editor Integration
**Files:**
- Create: `front/components/CodeEditor.tsx`
- Modify: `front/app/ba/v2/page.tsx`

- [ ] **Step 1: Install Monaco Editor dependencies**
```bash
npm install @monaco-editor/react
```
- [ ] **Step 2: Create CodeEditor component**
```typescript
// front/components/CodeEditor.tsx
import Editor from '@monaco-editor/react'

export default function CodeEditor({ code }: { code: string }) {
  return (
    <Editor
      height="500px"
      defaultLanguage="python"
      value={code}
      theme="vs-dark"
      options={{
        readOnly: true,
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
        folding: true,
        wordWrap: 'on'
      }}
    />
  )
}
```
- [ ] **Step 3: Replace basic code display with Monaco Editor**
```typescript
// In front/app/ba/v2/page.tsx, replace lines 426-444
{activeTab === 'code' && (
  <div className="bg-[#111720] border border-[#1e293b] rounded-2xl p-8 h-[500px] overflow-hidden">
    <CodeEditor code={latestStrategy?.code || '// No strategy code available'} />
  </div>
)}
```
- [ ] **Step 4: Commit**
```bash
git add front/components/CodeEditor.tsx front/app/ba/v2/page.tsx package.json package-lock.json
git commit -m "feat: integrate Monaco Editor for strategy code viewing"
```

### Task 5: Error Handling & Loading States
**Files:**
- Modify: `front/app/ba/v2/page.tsx`

- [ ] **Step 1: Add error handling for Supabase subscriptions**
```typescript
const [subscriptionError, setSubscriptionError] = useState<string | null>(null)

useEffect(() => {
  const subscription = supabase
    .channel('agent-performance')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'backtest_results' },
      (payload) => {
        // Handle updates
      }
    )
    .on('system', { event: 'ERROR' }, (err) => {
      setSubscriptionError('Real-time connection failed')
    })
    .subscribe((status) => {
      if (status === 'SUBSCRIBED') {
        setSubscriptionError(null)
      }
    })

  return () => subscription.unsubscribe()
}, [])
```
- [ ] **Step 2: Add reconnection logic**
```typescript
const handleReconnect = () => {
  // Reconnect logic
}
```
- [ ] **Step 3: Add loading states for initial data fetch**
```typescript
const [isLoadingData, setIsLoadingData] = useState(true)

useEffect(() => {
  const loadInitialData = async () => {
    try {
      setIsLoadingData(true)
      // Load initial data from Supabase
    } finally {
      setIsLoadingData(false)
    }
  }
  loadInitialData()
}, [])
```
- [ ] **Step 4: Commit**
```bash
git add front/app/ba/v2/page.tsx
git commit -m "feat: add error handling and loading states for real-time data"
```

### Task 6: Final Integration & Testing
**Files:**
- Modify: `front/app/ba/v2/page.tsx`
- Create: `front/app/ba/v2/layout.tsx`

- [ ] **Step 1: Create layout file for proper page structure**
```typescript
// front/app/ba/v2/layout.tsx
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0e14] text-white">
      {children}
    </div>
  )
}
```
- [ ] **Step 2: Test real-time functionality**
- Start the frontend and backend
- Trigger an evolution cycle in the backend
- Verify that the dashboard updates in real-time
- [ ] **Step 3: Commit**
```bash
git add front/app/ba/v2/layout.tsx front/app/ba/v2/page.tsx
git commit -m "feat: complete real-time dashboard integration"
```
