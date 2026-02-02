import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { Globe2, ListChecks, Info } from "lucide-react"
import { LeaguePicker } from "@/components/LeaguePicker"
import { cn } from "@/lib/utils"
import { getLeagues } from "@/api/teams"

export type SoccerMode = 'all' | 'manual' | null

interface SoccerModeSelectorProps {
  mode: SoccerMode
  onModeChange: (mode: SoccerMode) => void
  selectedLeagues: string[]
  onLeaguesChange: (leagues: string[]) => void
  className?: string
}

export function SoccerModeSelector({
  mode,
  onModeChange,
  selectedLeagues,
  onLeaguesChange,
  className,
}: SoccerModeSelectorProps) {
  // Fetch all leagues to filter for soccer
  const { data: leaguesResponse } = useQuery({
    queryKey: ["cached-leagues"],
    queryFn: () => getLeagues(),
  })

  // Get all soccer league slugs for display purposes
  const allSoccerLeagues = useMemo(() => {
    if (!leaguesResponse?.leagues) return []
    return leaguesResponse.leagues
      .filter(l => l.sport?.toLowerCase() === 'soccer')
      .map(l => l.slug)
  }, [leaguesResponse])

  const soccerLeagueCount = allSoccerLeagues.length

  const handleModeChange = (newMode: 'all' | 'manual') => {
    if (newMode === 'all') {
      onModeChange('all')
      // Clear explicit leagues when switching to all
      onLeaguesChange([])
    } else if (newMode === 'manual') {
      onModeChange('manual')
    }
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-col gap-3">
        {/* All Mode */}
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="radio"
            name="soccer-mode"
            checked={mode === 'all'}
            onChange={() => handleModeChange('all')}
            className="mt-1.5 h-4 w-4 border-muted-foreground text-primary focus:ring-primary"
          />
          <div className="flex-1">
            <span className="flex items-center gap-2 font-medium">
              <Globe2 className="h-4 w-4 text-muted-foreground" />
              All Soccer Leagues
            </span>
            <p className="text-sm text-muted-foreground mt-1">
              Automatically include all {soccerLeagueCount} enabled soccer leagues.
              New leagues are added automatically.
            </p>
          </div>
        </label>

        {/* Manual Mode */}
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="radio"
            name="soccer-mode"
            checked={mode === 'manual'}
            onChange={() => handleModeChange('manual')}
            className="mt-1.5 h-4 w-4 border-muted-foreground text-primary focus:ring-primary"
          />
          <div className="flex-1">
            <span className="flex items-center gap-2 font-medium">
              <ListChecks className="h-4 w-4 text-muted-foreground" />
              Select Leagues
            </span>
            <p className="text-sm text-muted-foreground mt-1">
              Choose specific leagues to include. Best for focused coverage.
            </p>
          </div>
        </label>
      </div>

      {/* League Picker - only shown in manual mode */}
      {mode === 'manual' && (
        <div className="pl-7 border-l-2 border-muted ml-2">
          <div className="flex items-center gap-2 mb-2 text-sm text-muted-foreground">
            <Info className="h-4 w-4" />
            <span>
              {selectedLeagues.length === 0
                ? "Select the soccer leagues you want to include"
                : `${selectedLeagues.length} league${selectedLeagues.length === 1 ? '' : 's'} selected`}
            </span>
          </div>
          <LeaguePicker
            selectedLeagues={selectedLeagues}
            onSelectionChange={onLeaguesChange}
            maxHeight="max-h-80"
            showSearch={true}
            showSelectedBadges={true}
            maxBadges={5}
            sportFilter="soccer"
          />
        </div>
      )}

      {/* All mode info */}
      {mode === 'all' && (
        <div className="pl-7 border-l-2 border-muted ml-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Info className="h-4 w-4" />
            <span>
              All {soccerLeagueCount} enabled soccer leagues will be included automatically.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
