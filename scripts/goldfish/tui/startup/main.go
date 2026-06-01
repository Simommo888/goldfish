package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"

	"goldfish/startup/internal/art"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

var (
	cBg      = lipgloss.Color("#02070A")
	cLine    = lipgloss.Color("#5D6264")
	cLineDim = lipgloss.Color("#30383C")
	cOrange  = lipgloss.Color("#FF941F")
	cOrange2 = lipgloss.Color("#FFB35A")
	cOrange3 = lipgloss.Color("#9A3D11")
	cCream   = lipgloss.Color("#FFE1A0")
	cCyan    = lipgloss.Color("#8EEEFF")
	cGreen   = lipgloss.Color("#73D86B")
	cBody    = lipgloss.Color("#F1E5D0")
	cMuted   = lipgloss.Color("#8A8F92")
	cPlant   = lipgloss.Color("#6F9A35")
	cRock    = lipgloss.Color("#6D5B3E")
	cBlack   = lipgloss.Color("#02070A")

	base    = lipgloss.NewStyle().Background(cBg)
	line    = lipgloss.NewStyle().Foreground(cLine).Background(cBg)
	dim     = lipgloss.NewStyle().Foreground(cLineDim).Background(cBg)
	title   = lipgloss.NewStyle().Foreground(cOrange).Background(cBg).Bold(true)
	orange  = lipgloss.NewStyle().Foreground(cOrange).Background(cBg)
	orange2 = lipgloss.NewStyle().
		Foreground(cOrange2).
		Background(cBg)
	orange3 = lipgloss.NewStyle().Foreground(cOrange3).Background(cBg)
	cyan    = lipgloss.NewStyle().Foreground(cCyan).Background(cBg)
	green   = lipgloss.NewStyle().Foreground(cGreen).Background(cBg)
	body    = lipgloss.NewStyle().Foreground(cBody).Background(cBg)
	muted   = lipgloss.NewStyle().Foreground(cMuted).Background(cBg)
	cream   = lipgloss.NewStyle().Foreground(cCream).Background(cBg)
	plant   = lipgloss.NewStyle().Foreground(cPlant).Background(cBg)
	rock    = lipgloss.NewStyle().Foreground(cRock).Background(cBg)
	dark    = lipgloss.NewStyle().Foreground(cBlack).Background(cBg)
)

type rect struct {
	X int `json:"x"`
	Y int `json:"y"`
	W int `json:"w"`
	H int `json:"h"`
}

type canvasSpec struct {
	Cols int `json:"cols"`
	Rows int `json:"rows"`
}

type layoutSpec struct {
	Canvas     canvasSpec `json:"canvas"`
	Hero       rect       `json:"hero"`
	Status     rect       `json:"status"`
	Sessions   rect       `json:"sessions"`
	QuickStart rect       `json:"quick_start"`
	Tools      rect       `json:"tools"`
	Tips       rect       `json:"tips"`
	CommandBar rect       `json:"command_bar"`
}

type sessionEntry struct {
	Name string `json:"name"`
	Time string `json:"time"`
}

type toolEntry struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

type startupState struct {
	Memory         any            `json:"memory"`
	Tools          any            `json:"tools"`
	ToolList       []toolEntry    `json:"tool_list"`
	Model          string         `json:"model"`
	Provider       string         `json:"provider"`
	Status         string         `json:"status"`
	Workspace      string         `json:"workspace"`
	Session        string         `json:"session"`
	RecentSessions []sessionEntry `json:"recent_sessions"`
}

type placement struct {
	box   rect
	lines []string
}

type model struct {
	width  int
	height int
	layout layoutSpec
	state  startupState
}

func main() {
	once := flag.Bool("once", false, "render once and exit")
	layoutPath := flag.String("layout", "", "path to startup layout json")
	statePath := flag.String("state", "", "path to startup state json")
	flag.Parse()

	layout := loadLayout(*layoutPath)
	state := loadState(*statePath)
	if *once {
		fmt.Print(Render(layout.Canvas.Cols+4, layout.Canvas.Rows+2, layout, state))
		return
	}

	p := tea.NewProgram(model{
		width:  layout.Canvas.Cols + 4,
		height: layout.Canvas.Rows + 2,
		layout: layout,
		state:  state,
	})
	if _, err := p.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q", "esc":
			return m, tea.Quit
		}
	}
	return m, nil
}

func (m model) View() string {
	return Render(m.width, m.height, m.layout, m.state)
}

func Render(width, height int, layout layoutSpec, state startupState) string {
	layout = normalizeLayout(layout)
	state = normalizeState(state)
	neededW := layout.Canvas.Cols + 4
	neededH := layout.Canvas.Rows + 2
	if width < neededW || height < neededH {
		return resizeView(width, height, neededW, neededH)
	}

	rows := compose(layout, state)
	return frame(rows, layout.Canvas.Cols)
}

func loadLayout(path string) layoutSpec {
	if path == "" {
		path = os.Getenv("GOLDFISH_STARTUP_LAYOUT")
	}
	if path == "" {
		if exe, err := os.Executable(); err == nil {
			candidate := filepath.Join(filepath.Dir(exe), "layout.json")
			if _, err := os.Stat(candidate); err == nil {
				path = candidate
			}
		}
	}
	if path == "" {
		if _, file, _, ok := runtime.Caller(0); ok {
			candidate := filepath.Join(filepath.Dir(file), "layout.json")
			if _, err := os.Stat(candidate); err == nil {
				path = candidate
			}
		}
	}
	if path == "" {
		return defaultLayout()
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return defaultLayout()
	}
	var layout layoutSpec
	if err := json.Unmarshal(data, &layout); err != nil {
		return defaultLayout()
	}
	return normalizeLayout(layout)
}

func loadState(path string) startupState {
	if path == "" {
		path = os.Getenv("GOLDFISH_STARTUP_STATE")
	}
	if path == "" {
		if exe, err := os.Executable(); err == nil {
			candidate := filepath.Join(filepath.Dir(exe), "startup_state.json")
			if _, err := os.Stat(candidate); err == nil {
				path = candidate
			}
		}
	}
	if path == "" {
		return defaultState()
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return defaultState()
	}
	data = bytes.TrimPrefix(data, []byte{0xEF, 0xBB, 0xBF})
	var state startupState
	if err := json.Unmarshal(data, &state); err != nil {
		return defaultState()
	}
	return normalizeState(state)
}

func defaultState() startupState {
	return startupState{
		Memory:         "on",
		Tools:          0,
		Model:          "not configured",
		Provider:       "local",
		Status:         "ready",
		Workspace:      "~/workspace",
		Session:        "new",
		ToolList:       []toolEntry{},
		RecentSessions: []sessionEntry{},
	}
}

func normalizeState(state startupState) startupState {
	defaults := defaultState()
	if valueString(state.Memory, "") == "" {
		state.Memory = defaults.Memory
	}
	if valueString(state.Tools, "") == "" {
		state.Tools = defaults.Tools
	}
	if state.Model == "" {
		state.Model = defaults.Model
	}
	if state.Provider == "" {
		state.Provider = defaults.Provider
	}
	if state.Status == "" {
		state.Status = defaults.Status
	}
	if state.Workspace == "" {
		state.Workspace = defaults.Workspace
	}
	if state.Session == "" {
		state.Session = defaults.Session
	}
	return state
}

func defaultLayout() layoutSpec {
	return layoutSpec{
		Canvas:     canvasSpec{Cols: 120, Rows: 40},
		Hero:       rect{X: 0, Y: 0, W: 72, H: 22},
		Status:     rect{X: 72, Y: 0, W: 48, H: 14},
		Sessions:   rect{X: 72, Y: 14, W: 48, H: 10},
		QuickStart: rect{X: 0, Y: 22, W: 36, H: 14},
		Tools:      rect{X: 36, Y: 22, W: 36, H: 14},
		Tips:       rect{X: 72, Y: 24, W: 48, H: 12},
		CommandBar: rect{X: 0, Y: 36, W: 120, H: 4},
	}
}

func normalizeLayout(layout layoutSpec) layoutSpec {
	if layout.Canvas.Cols <= 0 || layout.Canvas.Rows <= 0 {
		layout.Canvas = canvasSpec{Cols: 120, Rows: 40}
	}
	if layout.Hero.W <= 0 {
		return defaultLayout()
	}
	return layout
}

func compose(layout layoutSpec, state startupState) []string {
	rows := blankBlock(layout.Canvas.Cols, layout.Canvas.Rows)
	placements := []placement{
		{layout.Hero, hero(layout.Hero.W, layout.Hero.H)},
		{layout.Status, status(layout.Status.W, layout.Status.H, state)},
		{layout.Sessions, recentSessions(layout.Sessions.W, layout.Sessions.H, state)},
		{layout.QuickStart, quickStart(layout.QuickStart.W, layout.QuickStart.H)},
		{layout.Tools, availableTools(layout.Tools.W, layout.Tools.H, state)},
		{layout.Tips, tips(layout.Tips.W, layout.Tips.H)},
		{layout.CommandBar, commandBar(layout.CommandBar.W, layout.CommandBar.H)},
	}
	for y := 0; y < layout.Canvas.Rows; y++ {
		active := make([]placement, 0, len(placements))
		for _, p := range placements {
			if y >= p.box.Y && y < p.box.Y+p.box.H {
				active = append(active, p)
			}
		}
		sort.SliceStable(active, func(i, j int) bool {
			return active[i].box.X < active[j].box.X
		})

		var row strings.Builder
		x := 0
		for _, p := range active {
			if p.box.X > x {
				row.WriteString(strings.Repeat(" ", p.box.X-x))
			}
			localY := y - p.box.Y
			if localY >= 0 && localY < len(p.lines) {
				row.WriteString(p.lines[localY])
			} else {
				row.WriteString(strings.Repeat(" ", p.box.W))
			}
			x = p.box.X + p.box.W
		}
		if x < layout.Canvas.Cols {
			row.WriteString(strings.Repeat(" ", layout.Canvas.Cols-x))
		}
		rows[y] = fitLine(row.String(), layout.Canvas.Cols)
	}
	return rows
}

func hero(w, h int) []string {
	lines := []string{}
	lines = append(lines, heroLogo(w)...)
	lines = append(lines, center(cyan.Render("small agent, sharp memory"), w))
	lines = append(lines, "")
	welcome := center(orange.Render(". +")+" "+cyan.Render("welcome to your intelligence companion")+" "+orange.Render("+ ."), w)
	lines = append(lines, fishArtwork(w, max(0, h-len(lines)-1))...)
	lines = append(lines, welcome)
	return fitLines(lines, w, h)
}

func fishArtwork(w, h int) []string {
	raw := strings.TrimRight(art.Fish, "\r\n")
	if raw == "" {
		return fitLines(fishScene(w), w, h)
	}
	lines := strings.Split(raw, "\n")
	for i := range lines {
		lines[i] = strings.TrimRight(lines[i], "\r")
	}
	return fitLines(centerBlock(lines, w), w, h)
}

func heroLogo(w int) []string {
	rows := []string{
		" ██████   ██████  ██      ██████  ███████ ██ ███████ ██   ██ ",
		"██       ██    ██ ██      ██   ██ ██      ██ ██      ██   ██ ",
		"██   ███ ██    ██ ██      ██   ██ █████   ██ ███████ ███████",
		"██    ██ ██    ██ ██      ██   ██ ██      ██      ██ ██   ██ ",
		" ██████   ██████  ███████ ██████  ██      ██ ███████ ██   ██ ",
	}
	logo := pixelLogo3D(rows)
	out := make([]string, 0, len(logo))
	for i, row := range logo {
		text := row
		if i == 1 && lipgloss.Width(text)+lipgloss.Width(badge("v0.1.0"))+1 <= w {
			text += " " + badge("v0.1.0")
		}
		out = append(out, center(text, w))
	}
	return out
}

func pixelLogo3D(rows []string) []string {
	maxW := 0
	for _, row := range rows {
		maxW = max(maxW, len([]rune(row)))
	}

	h := len(rows) + 1
	w := maxW + 2
	cells := make([][]string, h)
	for y := range cells {
		cells[y] = make([]string, w)
		for x := range cells[y] {
			cells[y][x] = " "
		}
	}

	for y, row := range rows {
		for x, r := range []rune(row) {
			if r == ' ' {
				continue
			}
			sx := x + 2
			sy := y + 1
			if sy < h && sx < w {
				cells[sy][sx] = orange3.Render("▓")
			}
		}
	}

	for y, row := range rows {
		for x, r := range []rune(row) {
			if r == ' ' {
				continue
			}
			ch := string(r)
			if y == 0 || isTopEdge(rows, x, y) {
				cells[y][x] = orange2.Render(ch)
			} else {
				cells[y][x] = orange.Render(ch)
			}
		}
	}

	out := make([]string, 0, h)
	for _, row := range cells {
		out = append(out, strings.Join(row, ""))
	}
	return out
}

func isTopEdge(rows []string, x, y int) bool {
	if y == 0 {
		return true
	}
	prev := []rune(rows[y-1])
	return x >= len(prev) || prev[x] == ' '
}

func fishScene(w int) []string {
	raw := []string{
		"       o       O",
		"   ╭╮                    ▄▄████▄▄          ▄██▄",
		"  ╭╯╰╮               ▄▄██████████▄▄    ▄▄██████▄",
		" ╭╯  ╰╮           ▄████████████████▄▄▄████▀ ▀███",
		" ╰╮╭╮╭╯        ▄█████▓▓████████████████▀     ██▀",
		"  ╰╯╰╯      ▄██████▓▓ ●████████████████▄   ▄██▀",
		"  ▄▄▃▃    ▄████████▓▓▄██████████████████▄████▀",
		" ▀▀  ▀▀   ▀██████████████████████▀▀████████▀",
		"             ▀▀██████████████▀▀      ▀██▀",
		"       ▄▄        ▀▀██████▀▀         ▄█▀",
		"   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄▄▄▄▄▄▀▀▀▀▀▀▀▀▀▀▀▀",
	}
	out := make([]string, 0, len(raw))
	for i, row := range raw {
		switch {
		case i == 0:
			out = append(out, cyan.Render(row))
		case strings.ContainsAny(row, "╭╮╯╰─"):
			out = append(out, colorAquariumLine(row))
		default:
			out = append(out, colorFishLine(row))
		}
	}
	return centerBlock(out, w)
}

func status(w, h int, state startupState) []string {
	rows := []string{
		statusRow("mem", "memory", green.Render(valueString(state.Memory, "on"))),
		statusRow("tls", "tools", green.Render(valueString(state.Tools, "0"))),
		statusRow("mdl", "model", green.Render(compactPath(state.Model, 18))),
		statusRow("api", "provider", green.Render(compactPath(state.Provider, 18))),
		statusRow("run", "status", green.Render(valueString(state.Status, "ready"))),
		statusRow("dir", "workspace", body.Render(compactPath(state.Workspace, 18))),
		statusRow("new", "session", body.Render(compactPath(state.Session, 18))),
	}
	return panel(w, h, "><(((o> STATUS", rows)
}

func recentSessions(w, h int, state startupState) []string {
	rows := []string{}
	for i, item := range state.RecentSessions {
		if i >= 3 {
			break
		}
		name := item.Name
		if name == "" {
			name = "session"
		}
		timeText := item.Time
		if timeText == "" {
			timeText = "recent"
		}
		rows = append(rows, sessionLine(w-4, fmt.Sprintf("%d", i+1), compactPath(name, 22), timeText))
		if i < 2 {
			rows = append(rows, dim.Render(strings.Repeat("┄", max(0, w-4))))
		}
	}
	if len(rows) == 0 {
		rows = append(rows, muted.Render("no sessions yet"))
	}
	for len(rows) < 5 {
		rows = append(rows, "")
	}
	rows = append(rows, right(cyan.Render("more... (gf sessions)"), w-4))
	return panel(w, h, fmt.Sprintf("RECENT SESSIONS (%d)", min(3, len(state.RecentSessions))), rows)
}

func quickStart(w, h int) []string {
	rows := [][]string{
		{"/chat", "start a conversation"},
		{"/resume", "continue last task"},
		{"/memory", "inspect memory"},
		{"/tools", "list available tools"},
		{"/plan", "create a task plan"},
		{"/help", "show all commands"},
		{"/exit", "quit goldfish"},
	}
	return commandPanel(w, h, "QUICK START", rows, 10)
}

func availableTools(w, h int, state startupState) []string {
	rows := [][]string{}
	for _, tool := range state.ToolList {
		if len(rows) >= 6 {
			break
		}
		name := strings.ReplaceAll(tool.Name, "_", "-")
		rows = append(rows, []string{name, shortToolDescription(tool.Description)})
	}
	if len(rows) == 0 {
		rows = append(rows, []string{"no-tools", "run goldfish doctor"})
	}
	rows = append(rows, []string{"/tools", "more tools"})
	return commandPanel(w, h, fmt.Sprintf("AVAILABLE TOOLS (%s)", valueString(state.Tools, "0")), rows, 12)
}

func tips(w, h int) []string {
	rows := []string{
		orange.Render("+") + " " + body.Render("type / to see all commands"),
		orange.Render("+") + " " + body.Render("use up/down for history"),
		orange.Render("+") + " " + body.Render("ctrl+c to interrupt"),
		orange.Render("+") + " " + body.Render("goldfish remembers what matters"),
		orange.Render("+") + " " + body.Render("your data stays in your control"),
		"",
		right(plant.Render("╭╮ ")+orange.Render("><(((o>")+cyan.Render(" o o"), w-4),
	}
	return panel(w, h, "TIPS", rows)
}

func commandBar(w, h int) []string {
	rows := []string{line.Render(strings.Repeat("─", w))}
	for len(rows) < h {
		rows = append(rows, "")
	}
	return fitLines(rows, w, h)
}

func commandPanel(w, h int, name string, rows [][]string, gap int) []string {
	bodyRows := make([]string, 0, len(rows))
	for _, row := range rows {
		left := green.Render(row[0])
		bodyRows = append(bodyRows, left+strings.Repeat(" ", max(2, gap-lipgloss.Width(row[0])))+body.Render(row[1]))
	}
	return panel(w, h, name, bodyRows)
}

func panel(w, h int, name string, rows []string) []string {
	inner := max(1, w-4)
	out := []string{}
	titleText := " " + name + " "
	rightLen := max(0, w-4-lipgloss.Width(titleText))
	out = append(out, line.Render("┌─")+title.Render(titleText)+line.Render(strings.Repeat("─", rightLen)+"┐"))

	bodyH := max(0, h-2)
	for i := 0; i < bodyH; i++ {
		text := ""
		if i < len(rows) {
			text = rows[i]
		}
		out = append(out, line.Render("│ ")+fitLine(text, inner)+line.Render(" │"))
	}
	out = append(out, line.Render("└"+strings.Repeat("─", w-2)+"┘"))
	return fitLines(out, w, h)
}

func colorAquariumLine(s string) string {
	var b strings.Builder
	for _, r := range s {
		ch := string(r)
		switch r {
		case '╭', '╮', '╯', '╰', '─':
			b.WriteString(plant.Render(ch))
		case '▄', '▀', '▃':
			b.WriteString(rock.Render(ch))
		case 'o', 'O':
			b.WriteString(cyan.Render(ch))
		default:
			b.WriteString(ch)
		}
	}
	return b.String()
}

func colorFishLine(s string) string {
	var b strings.Builder
	for _, r := range s {
		ch := string(r)
		switch r {
		case '█', '▄', '▀':
			b.WriteString(orange.Render(ch))
		case '▓':
			b.WriteString(orange2.Render(ch))
		case '▒':
			b.WriteString(cream.Render(ch))
		case '●':
			b.WriteString(dark.Render(ch))
		default:
			b.WriteString(ch)
		}
	}
	return b.String()
}

func statusRow(icon, key, value string) string {
	return muted.Render(icon) + "  " + body.Render(key) + strings.Repeat(" ", max(1, 12-len(key))) + line.Render(": ") + value
}

func sessionLine(w int, num, name, age string) string {
	left := green.Render(num) + "  " + body.Render(name)
	space := max(2, w-lipgloss.Width(num)-2-lipgloss.Width(name)-lipgloss.Width(age))
	return left + strings.Repeat(" ", space) + muted.Render(age)
}

func badge(text string) string {
	return line.Render("╭─") + body.Render(" "+text+" ") + line.Render("─╮")
}

func frame(content []string, innerW int) string {
	out := []string{}
	out = append(out, line.Render("┌"+strings.Repeat("─", innerW+2)+"┐"))
	for _, row := range content {
		out = append(out, line.Render("│ ")+fitLine(row, innerW)+line.Render(" │"))
	}
	out = append(out, line.Render("└"+strings.Repeat("─", innerW+2)+"┘"))
	return base.Render(strings.Join(out, "\n"))
}

func resizeView(width, height, neededW, neededH int) string {
	lines := []string{
		title.Render("goldfish"),
		"",
		body.Render("Terminal is too small for the JSON-driven startup screen."),
		body.Render(fmt.Sprintf("Minimum: %d columns x %d rows", neededW, neededH)),
		body.Render(fmt.Sprintf("Current: %d columns x %d rows", width, height)),
		"",
		cyan.Render("Resize the terminal, then run goldfish again."),
	}
	return base.Padding(1, 2).Render(strings.Join(lines, "\n"))
}

func blankBlock(w, h int) []string {
	out := make([]string, h)
	for i := range out {
		out[i] = strings.Repeat(" ", w)
	}
	return out
}

func fitLines(lines []string, w, h int) []string {
	out := make([]string, 0, h)
	for i := 0; i < h; i++ {
		if i < len(lines) {
			out = append(out, fitLine(lines[i], w))
		} else {
			out = append(out, strings.Repeat(" ", w))
		}
	}
	return out
}

func fitLine(s string, w int) string {
	if lipgloss.Width(s) > w {
		return s
	}
	return s + strings.Repeat(" ", w-lipgloss.Width(s))
}

func centerBlock(lines []string, w int) []string {
	out := make([]string, len(lines))
	for i, row := range lines {
		out[i] = center(row, w)
	}
	return out
}

func center(s string, w int) string {
	space := max(0, w-lipgloss.Width(s))
	return strings.Repeat(" ", space/2) + s + strings.Repeat(" ", space-space/2)
}

func right(s string, w int) string {
	space := max(0, w-lipgloss.Width(s))
	return strings.Repeat(" ", space) + s
}

func valueString(value any, fallback string) string {
	switch v := value.(type) {
	case nil:
		return fallback
	case string:
		if v == "" {
			return fallback
		}
		return v
	case float64:
		return fmt.Sprintf("%.0f", v)
	case int:
		return fmt.Sprintf("%d", v)
	case int64:
		return fmt.Sprintf("%d", v)
	case bool:
		if v {
			return "on"
		}
		return "off"
	default:
		text := fmt.Sprintf("%v", v)
		if text == "" {
			return fallback
		}
		return text
	}
}

func compactPath(value string, maxWidth int) string {
	if lipgloss.Width(value) <= maxWidth {
		return value
	}
	value = strings.ReplaceAll(value, "\\", "/")
	parts := strings.Split(value, "/")
	if len(parts) > 1 {
		short := "..." + "/" + parts[len(parts)-1]
		if lipgloss.Width(short) <= maxWidth {
			return short
		}
	}
	runes := []rune(value)
	if maxWidth <= 1 {
		return "…"
	}
	for len(runes) > 0 && lipgloss.Width("…"+string(runes)) > maxWidth {
		runes = runes[1:]
	}
	return "…" + string(runes)
}

func shortToolDescription(description string) string {
	text := strings.ToLower(description)
	switch {
	case strings.Contains(text, "public web"):
		return "search the web"
	case strings.Contains(text, "daily"):
		return "daily workflow"
	case strings.Contains(text, "without writing"):
		return "dry run"
	case strings.Contains(text, "weekly"):
		return "weekly report"
	case strings.Contains(text, "config"):
		return "check config"
	case strings.Contains(text, "diagnose"):
		return "diagnose setup"
	case strings.Contains(text, "memory"):
		return "inspect memory"
	case strings.Contains(text, "feedback"):
		return "list feedback"
	case strings.Contains(text, "history") || strings.Contains(text, "recent"):
		return "recent runs"
	case strings.Contains(text, "search"):
		return "search memory"
	case strings.Contains(text, "skills"):
		return "list skills"
	case strings.Contains(text, "source"):
		return "source health"
	case strings.Contains(text, "agent loop"):
		return "agent loop"
	case strings.Contains(text, "available tools"):
		return "list tools"
	}
	if description == "" {
		return "available"
	}
	return compactPath(description, 18)
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
