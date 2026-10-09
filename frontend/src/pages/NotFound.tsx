import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Card, EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <Card>
      <EmptyState
        icon={<Compass className="size-5" />}
        title="Page not found"
        action={
          <Link className="text-sm font-medium text-indigo-600 hover:underline" to="/dashboard">
            Go to dashboard
          </Link>
        }
      >
        The page you're looking for doesn't exist.
      </EmptyState>
    </Card>
  )
}
