import ConversationSidebar from './components/ConversationSidebar'
import ConversationPage from './pages/ConversationPage'

const convId = new URLSearchParams(window.location.search).get('conv_id') || ''

export default function App() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <ConversationSidebar activeId={convId} />

      <main className="flex-1 overflow-y-auto">
        {convId ? (
          <ConversationPage convId={convId} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-center px-4">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5" className="mb-4">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="text-sm text-gray-500 font-medium">Chọn hội thoại hoặc tạo mới</p>
            <p className="text-xs text-gray-400 mt-1">Mỗi hội thoại là một phiên thẩm định độc lập</p>
          </div>
        )}
      </main>
    </div>
  )
}
