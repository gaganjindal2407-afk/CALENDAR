## The idea
I want a calendar that never ends. I should be able to browse any month or year,
past or future, as far as I like, and save events on specific dates. Some events,
like anniversaries and birthdays, should come back every year on their own.

## Calendar features
- Show a month grid, opening on the current month, with today highlighted.
- Next/previous buttons, and left/right arrow keys to move between months.
- A jump-to-date option so I can pick any month and year from 1 to 9999.
- A year view so I can quickly pick a month.
- A "Today" button to bring me back home.
- Get leap years and month lengths right (the calendar module should help here).

## Event features
- Let me click a date and add an event with a title, date, optional time, notes,
  and a category (Anniversary, Birthday, Holiday, Personal, or Other).
- I should be able to edit and delete events.
- Days with events should show a small colored marker based on category.
- Clicking a day should show that day's events in a side panel.

## Yearly repeats
- Add a "Repeat every year" checkbox, ticked by default for Anniversary and
  Birthday.
- Only store the original date, and work out the repeats on the fly, so we never
  create endless records.
- Show the count on each repeat, like "5th Anniversary" or "Turns 30", and don't
  show the event in years before the original one.
- For Feb 29 events, show them on Feb 28 in non-leap years, and add a setting to
  switch that to Mar 1.

## Reminders
- For each event, let me choose when to be reminded: on the day, 1 day before,
  1 week before, 1 month before, or a custom number of days.
- For yearly events, the reminders should repeat every year too.
- Add an "Upcoming" panel that lists the next 30 days of events and reminders.
- When the app opens, pop up anything that's due today.
- While it's running, check every minute for timed reminders and send a desktop
  notification (use plyer if it's installed, otherwise a Tkinter popup).

## Saving data
- Keep events in a local events.json file (or SQLite, if you think that's
  better). Load it on startup and save after every change.
- Use this structure for each event:
  { id, title, start_date (YYYY-MM-DD), time, notes, category,
    repeat_yearly (bool), reminders: [days_before] }
- Let me export and import events as JSON for backups.


## Look and feel
- Keep it clean and easy to read, with color-coded categories.
- Include a light/dark theme toggle.
- Add keyboard shortcuts, and make the window resize sensibly.

The code should be easily understandable and it should also take in account the 29th february event
