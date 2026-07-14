'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import ShellLayout from '@/components/layout/ShellLayout'

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isBareRoute = pathname === '/login'

  if (isBareRoute) {
    return <>{children}</>
  }

  return <ShellLayout>{children}</ShellLayout>
}
