import { useEffect, useState } from 'react'
import { LayoutDashboard, CalendarDays, ClipboardList, BookOpen, Bell, Bot, Search, Plus, ArrowUpRight, CheckCircle2, Clock3, Sparkles, Send, Menu, X, MoreHorizontal, BrainCircuit, CalendarCheck, CircleCheck, AlertCircle, Trash2, ChevronLeft, ChevronRight, LogOut } from 'lucide-react'
import AuthPage from './AuthPage.jsx'
import { api } from './api.js'

const nav = [
  ['Overview', LayoutDashboard], ['Assignments', ClipboardList], ['Calendar', CalendarDays],
  ['Timetable', BookOpen], ['AI Assistant', Bot], ['Notifications', Bell]
]
const todayLabel = new Intl.DateTimeFormat('en', { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date())
const isoToday = new Date().toISOString().slice(0,10)
function App() {
  const [page,setPage] = useState('Overview')
  const [mobile,setMobile] = useState(false)
  const [user,setUser] = useState(null)
  const [authReady,setAuthReady] = useState(false)
  const [authError,setAuthError] = useState('')
  const [dashboard,setDashboard] = useState(null)
  const [assignments,setAssignments] = useState([])
  const [classes,setClasses] = useState([])
  const [events,setEvents] = useState([])
  const [chat,setChat] = useState([{role:'assistant', text:"Hi! I'm your StudentDesk AI assistant. I can add assignments, check your classes, and create calendar events. What would you like to organize today?"}])
  const [message,setMessage] = useState('')
  const [busy,setBusy] = useState(false)
  const [notice,setNotice] = useState('')
  const [showAssignment,setShowAssignment] = useState(false)
  const [showEvent,setShowEvent] = useState(false)
  const [assignmentForm,setAssignmentForm] = useState({title:'',subject:'',due_date:'',priority:'Medium',description:''})
  const [eventForm,setEventForm] = useState({title:'',event_date:isoToday,event_time:'09:00',category:'Event',notes:''})
  const [month,setMonth] = useState(new Date())
  const [search,setSearch] = useState('')

  useEffect(()=>{
    let active = true
    api('/api/auth/me')
      .then(data=>{ if(active && data.authenticated) setUser(data.user) })
      .catch(error=>{ if(active) setAuthError(`Could not connect to StudentDesk: ${error.message}`) })
      .finally(()=>{ if(active) setAuthReady(true) })
    return ()=>{ active = false }
  },[])
  async function refresh() {
    try {
      const [d,a,c,e] = await Promise.all([api('/api/dashboard'),api('/api/assignments'),api('/api/classes'),api('/api/events')])
      setDashboard(d); setAssignments(a); setClasses(c); setEvents(e)
    } catch (e) { setNotice(`Backend connection: ${e.message}. Start the Flask server to load live data.`) }
  }
  useEffect(()=>{
    if (!user || !('Notification' in window) || Notification.permission !== 'granted') return
    const check = () => {
      const now = new Date()
      events.forEach(ev => {
        if (ev.event_date !== now.toISOString().slice(0,10)) return
        const [h,m] = (ev.event_time || '09:00').split(':').map(Number)
        if (now.getHours() === h && now.getMinutes() === m) new Notification('StudentDesk reminder', {body: ev.title})
      })
    }
    const id = setInterval(check, 30000)
    return ()=>clearInterval(id)
  },[events])
  useEffect(()=>{ if(user) refresh() },[user])
  const pending = assignments.filter(a=>a.status!=='Completed')
  const filtered = assignments.filter(a=>(a.title+' '+a.subject).toLowerCase().includes(search.toLowerCase()))
  const upcoming = [...events].sort((a,b)=>(a.event_date+a.event_time).localeCompare(b.event_date+b.event_time)).slice(0,4)
  const flash = (msg)=>{setNotice(msg); setTimeout(()=>setNotice(''),4000)}
  async function saveAssignment(e) {
    e.preventDefault()
    try { await api('/api/assignments',{method:'POST',body:JSON.stringify(assignmentForm)}); setShowAssignment(false); setAssignmentForm({title:'',subject:'',due_date:'',priority:'Medium',description:''}); await refresh(); flash('Assignment saved successfully.') }
    catch(err){flash(err.message)}
  }
  async function toggleAssignment(a) {
    try { await api(`/api/assignments/${a.id}`,{method:'PATCH',body:JSON.stringify({status:a.status==='Completed'?'Pending':'Completed'})}); await refresh() }
    catch(err){flash(err.message)}
  }
  async function removeAssignment(id) {
    try { await api(`/api/assignments/${id}`,{method:'DELETE'}); await refresh(); flash('Assignment deleted.') } catch(err){flash(err.message)}
  }
  async function saveEvent(e) {
    e.preventDefault()
    try { await api('/api/events',{method:'POST',body:JSON.stringify(eventForm)}); setShowEvent(false); setEventForm({title:'',event_date:isoToday,event_time:'09:00',category:'Event',notes:''}); await refresh(); flash('Calendar event created.') }
    catch(err){flash(err.message)}
  }
  async function sendChat(e) {
    e.preventDefault(); if(!message.trim() || busy) return
    const text = message.trim(); setChat(c=>[...c,{role:'user',text}]); setMessage(''); setBusy(true)
    try { const result=await api('/api/agent/chat',{method:'POST',body:JSON.stringify({message:text})}); setChat(c=>[...c,{role:'assistant',text:result.reply}]); await refresh() }
    catch(err){setChat(c=>[...c,{role:'assistant',text:err.message}])}
    setBusy(false)
  }
  async function askPermission(){ if('Notification' in window){const p=await Notification.requestPermission();flash(p==='granted'?'Browser notifications enabled.':'Notification permission was not granted.')}else flash('This browser does not support notifications.') }
  async function logout() {
    try {
      await api('/api/auth/logout',{method:'POST'})
      setUser(null); setDashboard(null); setAssignments([]); setClasses([]); setEvents([])
      setChat([{role:'assistant', text:"Hi! I'm your StudentDesk AI assistant. I can add assignments, check your classes, and create calendar events. What would you like to organize today?"}])
      setPage('Overview')
    } catch (error) {
      flash(error.message)
    }
  }
  const heading = page==='Overview'?'Your academic command center':page==='AI Assistant'?'Plan smarter with your AI agent':`Manage your ${page.toLowerCase()}`
  if (!authReady) return <div className="auth-loading" role="status">Loading your secure workspace…</div>
  if (!user) return <AuthPage backendError={authError} onAuthenticated={account=>{setAuthError('');setUser(account)}} />
  return <div className="app-shell">
    <aside className={`sidebar ${mobile?'mobile-open':''}`}>
      <div className="brand"><div className="brand-mark"><BrainCircuit size={22}/></div><div><b>StudentDesk<span>AI</span></b><small>SMART ACADEMIC PLANNER</small></div><button className="mobile-close" onClick={()=>setMobile(false)}><X/></button></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(([label,Icon])=><button key={label} className={`nav-item ${page===label?'active':''}`} onClick={()=>{setPage(label);setMobile(false)}}><Icon size={18}/><span>{label}</span>{label==='Notifications'&&events.length>0&&<i>{events.length}</i>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="upgrade-card"><div className="upgrade-icon"><Sparkles size={17}/></div><b>Stay ahead of your goals</b><p>Keep your semester organized, one task at a time.</p><button onClick={()=>setPage('AI Assistant')}>Talk to your AI <ArrowUpRight size={14}/></button></div><div className="profile"><div className="avatar">{user.name.slice(0,1).toUpperCase()}</div><div className="profile-details"><b>{user.name}</b><small>{user.email}</small></div><button className="profile-logout" onClick={logout} title="Log out" aria-label="Log out"><LogOut size={17}/></button></div></div>
    </aside>
    {mobile&&<div className="scrim" onClick={()=>setMobile(false)} />}
    <main className="main-area">
      <header className="topbar"><button className="menu-btn" onClick={()=>setMobile(true)}><Menu/></button><div className="breadcrumb">Workspace <span>/</span> <b>{page}</b></div><div className="top-actions"><div className="searchbox"><Search size={16}/><input placeholder="Search anything..." value={search} onChange={e=>setSearch(e.target.value)}/><kbd>⌘ K</kbd></div><button className="icon-btn" onClick={askPermission} title="Enable notifications"><Bell size={18}/><em/></button><div className="top-avatar">{user.name.slice(0,1).toUpperCase()}</div></div></header>
      <div className="content">
        <div className="page-heading"><div><div className="eyebrow"><span className="live-dot"/> YOUR STUDY SPACE</div><h1>{page==='Overview'?'Good day, student':page}</h1><p>{page==='Overview'?`Here’s what’s happening with your studies. ${todayLabel}.`:heading}</p></div><div className="heading-actions"><button className="btn btn-light" onClick={()=>setShowEvent(true)}><CalendarDays size={16}/> Add event</button><button className="btn btn-primary" onClick={()=>setShowAssignment(true)}><Plus size={17}/> New assignment</button></div></div>
        {notice&&<div className="toast"><AlertCircle size={16}/>{notice}<button onClick={()=>setNotice('')}><X size={15}/></button></div>}
        {page==='Overview'&&<><section className="hero-card"><div className="hero-copy"><div className="hero-pill"><Sparkles size={13}/> YOUR PERSONAL AI PLANNER</div><h2>Make space for<br/><span>what matters.</span></h2><p>Your AI-powered study companion keeps deadlines, classes and plans in one calm place.</p><button onClick={()=>setPage('AI Assistant')} className="hero-button">Chat with StudentDesk AI <ArrowUpRight size={16}/></button></div><div className="hero-art"><div className="orb orb-one"/><div className="orb orb-two"/><div className="floating-card card-a"><CalendarCheck size={19}/><span><b>Stay on track</b><small>One day at a time</small></span></div><div className="floating-card card-b"><Sparkles size={20}/><span><b>AI powered</b><small>Plan with clarity</small></span></div><div className="hero-illustration"><div className="illustration-screen"><div className="screen-top"><i/><i/><i/></div><div className="screen-lines"><b/><b/><b/></div><div className="screen-check"><CheckCircle2 size={30}/></div></div><div className="illustration-base"/></div></div></section>
          <div className="stats-grid"><Stat icon={ClipboardList} label="Total assignments" value={dashboard?.total_assignments??'—'} note="Across all subjects" color="purple"/><Stat icon={Clock3} label="Pending tasks" value={dashboard?.pending_assignments??'—'} note="Keep making progress" color="orange"/><Stat icon={CircleCheck} label="Completed" value={dashboard?.completed_assignments??'—'} note="Great work so far" color="green"/><Stat icon={CalendarDays} label="Upcoming events" value={dashboard?.upcoming_events??'—'} note="On your calendar" color="blue"/></div>
          <div className="dashboard-grid"><section className="panel assignments-panel"><div className="panel-head"><div><h3>Priority assignments</h3><p>Your next tasks to focus on</p></div><button className="text-link" onClick={()=>setPage('Assignments')}>View all <ArrowUpRight size={14}/></button></div><AssignmentList items={pending.slice(0,4)} onToggle={toggleAssignment}/>{pending.length===0&&<Empty text="No pending assignments. You're all caught up!"/>}</section><section className="panel"><div className="panel-head"><div><h3>Coming up</h3><p>Events on your horizon</p></div><button className="round-add" onClick={()=>setShowEvent(true)}><Plus size={17}/></button></div>{upcoming.map(ev=><div className="event-row" key={ev.id}><div className="event-date"><b>{new Date(ev.event_date+'T12:00:00').getDate()}</b><small>{new Date(ev.event_date+'T12:00:00').toLocaleString('en',{month:'short'})}</small></div><div className="event-info"><b>{ev.title}</b><small>{ev.event_time} · {ev.category}</small></div></div>)}{upcoming.length===0&&<Empty text="No upcoming events yet."/>}</section></div></>}
        {page==='Assignments'&&<section className="panel full-panel"><div className="panel-head"><div><h3>All assignments</h3><p>Track deadlines and celebrate your progress.</p></div><button className="btn btn-primary" onClick={()=>setShowAssignment(true)}><Plus size={16}/> Add assignment</button></div><AssignmentList items={filtered} onToggle={toggleAssignment} onDelete={removeAssignment} detailed/>{filtered.length===0&&<Empty text="No assignments found. Add your first task."/>}</section>}
        {page==='Calendar'&&<section className="panel calendar-panel"><div className="panel-head"><div><h3>Academic calendar</h3><p>Keep important dates in view.</p></div><button className="btn btn-primary" onClick={()=>setShowEvent(true)}><Plus size={16}/> Add event</button></div><div className="month-head"><button onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}><ChevronLeft/></button><h2>{month.toLocaleString('en',{month:'long',year:'numeric'})}</h2><button onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}><ChevronRight/></button></div><div className="calendar-grid">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=><b className="weekday" key={d}>{d}</b>)}{Array.from({length:new Date(month.getFullYear(),month.getMonth(),1).getDay()},(_,i)=><div key={'blank'+i}/>)}{Array.from({length:new Date(month.getFullYear(),month.getMonth()+1,0).getDate()},(_,i)=>{const day=i+1;const key=`${month.getFullYear()}-${String(month.getMonth()+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;const dayEvents=events.filter(e=>e.event_date===key);return <div className={`calendar-day ${key===isoToday?'today':''}`} key={day}><span>{day}</span>{dayEvents.map(ev=><small key={ev.id}>{ev.title}</small>)}</div>})}</div></section>}
        {page==='Timetable'&&<section className="panel full-panel"><div className="panel-head"><div><h3>Your weekly timetable</h3><p>Class schedule and classroom details.</p></div><span className="soft-tag">Sample entries included</span></div><div className="table-wrap"><table><thead><tr><th>Subject</th><th>Day</th><th>Time</th><th>Teacher</th><th>Room</th></tr></thead><tbody>{classes.map(c=><tr key={c.id}><td><b>{c.subject}</b></td><td>{c.day}</td><td>{c.start_time} – {c.end_time}</td><td>{c.teacher||'—'}</td><td><span className="room-tag">{c.room||'TBA'}</span></td></tr>)}</tbody></table></div></section>}
        {page==='AI Assistant'&&<section className="chat-layout"><div className="panel chat-panel"><div className="chat-head"><div className="ai-avatar"><Bot/></div><div><h3>StudentDesk AI</h3><p><span className="live-dot"/> Academic assistant · Tool-enabled</p></div><span className="online-tag">ONLINE</span></div><div className="chat-messages">{chat.map((m,i)=><div className={`message ${m.role}`} key={i}><div className="message-avatar">{m.role==='assistant'?<Sparkles size={15}/>: 'S'}</div><div className="bubble">{m.text}</div></div>)}{busy&&<div className="typing">StudentDesk AI is thinking…</div>}</div><div className="suggestions"><button onClick={()=>setMessage('Show my pending assignments')}>Show pending assignments</button><button onClick={()=>setMessage('What classes do I have on Monday?')}>Check Monday classes</button><button onClick={()=>setMessage('Create a study event for 2026-11-25 at 16:00')}>Create a study event</button></div><form className="chat-input" onSubmit={sendChat}><input value={message} onChange={e=>setMessage(e.target.value)} placeholder="Ask me to organize your study life…"/><button disabled={busy||!message.trim()}><Send size={17}/></button></form></div><aside className="panel agent-side"><div className="agent-side-icon"><Sparkles/></div><h3>Your study co-pilot</h3><p>Give a natural-language instruction. The agent can use connected tools to save assignments, retrieve your timetable and create calendar events.</p><div className="tool-line"><CheckCircle2/> Add and retrieve assignments</div><div className="tool-line"><CheckCircle2/> Check your class timetable</div><div className="tool-line"><CheckCircle2/> Create calendar events</div></aside></section>}
        {page==='Notifications'&&<section className="panel full-panel"><div className="panel-head"><div><h3>Reminder center</h3><p>Browser reminders work while this app is open.</p></div><button className="btn btn-primary" onClick={askPermission}><Bell size={16}/> Enable notifications</button></div>{events.map(ev=><div className="event-row" key={ev.id}><div className="event-date"><b>{new Date(ev.event_date+'T12:00:00').getDate()}</b><small>{new Date(ev.event_date+'T12:00:00').toLocaleString('en',{month:'short'})}</small></div><div className="event-info"><b>{ev.title}</b><small>{ev.event_date} at {ev.event_time} · {ev.category}</small></div></div>)}{events.length===0&&<Empty text="Your reminders will appear here."/>}</section>}
        <footer>© 2026 StudentDesk AI <span>Designed to make student life feel more organized.</span></footer>
      </div>
    </main>
    {showAssignment&&<Modal title="Create assignment" close={()=>setShowAssignment(false)}><form className="modal-form" onSubmit={saveAssignment}><Field label="Assignment title"><input required value={assignmentForm.title} onChange={e=>setAssignmentForm({...assignmentForm,title:e.target.value})} placeholder="e.g. Database project"/></Field><div className="form-row"><Field label="Subject"><input value={assignmentForm.subject} onChange={e=>setAssignmentForm({...assignmentForm,subject:e.target.value})} placeholder="e.g. Database Systems"/></Field><Field label="Due date"><input type="date" required value={assignmentForm.due_date} onChange={e=>setAssignmentForm({...assignmentForm,due_date:e.target.value})}/></Field></div><div className="form-row"><Field label="Priority"><select value={assignmentForm.priority} onChange={e=>setAssignmentForm({...assignmentForm,priority:e.target.value})}><option>Low</option><option>Medium</option><option>High</option></select></Field><Field label="Description"><input value={assignmentForm.description} onChange={e=>setAssignmentForm({...assignmentForm,description:e.target.value})} placeholder="Optional details"/></Field></div><button className="btn btn-primary modal-submit">Save assignment</button></form></Modal>}
    {showEvent&&<Modal title="Add calendar event" close={()=>setShowEvent(false)}><form className="modal-form" onSubmit={saveEvent}><Field label="Event title"><input required value={eventForm.title} onChange={e=>setEventForm({...eventForm,title:e.target.value})} placeholder="e.g. Project presentation"/></Field><div className="form-row"><Field label="Date"><input type="date" required value={eventForm.event_date} onChange={e=>setEventForm({...eventForm,event_date:e.target.value})}/></Field><Field label="Time"><input type="time" value={eventForm.event_time} onChange={e=>setEventForm({...eventForm,event_time:e.target.value})}/></Field></div><Field label="Category"><select value={eventForm.category} onChange={e=>setEventForm({...eventForm,category:e.target.value})}><option>Event</option><option>Exam</option><option>Study</option><option>Class</option></select></Field><button className="btn btn-primary modal-submit">Save event</button></form></Modal>}
  </div>
}
function Stat({icon:Icon,label,value,note,color}){return <div className="stat-card"><div className={`stat-icon ${color}`}><Icon size={19}/></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>}
function AssignmentList({items,onToggle,onDelete,detailed=false}){return <div className="assignment-list">{items.map(a=><div className="assignment-row" key={a.id}><button className={`task-check ${a.status==='Completed'?'checked':''}`} onClick={()=>onToggle(a)}><CheckCircle2 size={18}/></button><div className="task-main"><b className={a.status==='Completed'?'done':''}>{a.title}</b><small>{a.subject} · Due {a.due_date}</small></div><span className={`priority ${a.priority.toLowerCase()}`}>{a.priority}</span><span className={`status ${a.status.toLowerCase().replace(' ','-')}`}>{a.status}</span>{detailed&&<button className="delete-btn" onClick={()=>onDelete(a.id)} title="Delete"><Trash2 size={16}/></button>}</div>)}</div>}
function Empty({text}){return <div className="empty"><div><ClipboardList size={22}/></div>{text}</div>}
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
function Modal({title,close,children}){return <div className="modal-backdrop" onMouseDown={close}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><h3>{title}</h3><button onClick={close}><X/></button></div>{children}</div></div>}
export default App
