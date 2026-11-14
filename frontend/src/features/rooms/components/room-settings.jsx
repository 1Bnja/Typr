import Select from '../../../components/select/select'
import { AUTOMATIC_TIME_LIMIT, SETTING_FIELDS } from '../constants'

const RoomSettings = ({ settings, onChange, disabled = false }) => (
  <fieldset className="room-settings" disabled={disabled}>
    <legend className="sr-only">Room settings</legend>
    {SETTING_FIELDS.map(({ key, label, options }) => (
      <Select
        key={key}
        label={label}
        // El tiempo límite automático viaja como null en la API.
        value={settings[key] ?? AUTOMATIC_TIME_LIMIT}
        options={options}
        onChange={(value) => onChange(key, value === AUTOMATIC_TIME_LIMIT ? null : value)}
      />
    ))}
  </fieldset>
)

export default RoomSettings
