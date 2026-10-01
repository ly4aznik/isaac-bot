local IsaacBot = RegisterMod("Isaac Bot Bridge", 1)
local PROTOCOL = 1
local PORT = 21666
local OBSERVATION_INTERVAL = 2
local WATCHDOG_FRAMES = 15

local ok, socket = pcall(require, "socket")
local udp, peerIp, peerPort = nil, nil, nil
local observers = {}
local currentGoal = nil
local lastPacketFrame = -10000
local lastActionSequence = 0
local autoRestart = true
local roomWasClear = false
local runId = 0
local roomVisit = 0
local action = { moveX=0, moveY=0, shootX=0, shootY=0, bomb=false, item=false, pill=false, card=false, drop=false }
local previousButtons = {}

local function esc(value)
  local text = tostring(value or "")
  return text:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n")
end

local function bool(value) return value and "true" or "false" end
local function num(value)
  value = tonumber(value) or 0
  if value ~= value or value == math.huge or value == -math.huge then return "0" end
  return string.format("%.4f", value)
end

local function send(payload)
  if not udp then return end
  if peerIp then udp:sendto(payload, peerIp, peerPort) end
  local frame = Game():GetFrameCount()
  for key, observer in pairs(observers) do
    if frame - observer.lastFrame > 120 then
      observers[key] = nil
    elseif observer.ip ~= peerIp or observer.port ~= peerPort then
      udp:sendto(payload, observer.ip, observer.port)
    end
  end
end

local function sendEvent(name, extra)
  send(string.format(
    '{"v":%d,"type":"event","event":"%s","frame":%d,"run_id":%d,"room_visit":%d%s}',
    PROTOCOL, esc(name), Game():GetFrameCount(), runId, roomVisit, extra or ""
  ))
end

if ok then
  udp = socket.udp()
  udp:settimeout(0)
  local bound, bindError = udp:setsockname("127.0.0.1", PORT)
  if not bound then
    Isaac.DebugString("ISAAC BOT: UDP bind failed: " .. tostring(bindError))
    udp = nil
  else
    Isaac.DebugString("ISAAC BOT: protocol v" .. PROTOCOL .. " listening on 127.0.0.1:" .. PORT)
  end
else
  Isaac.DebugString("ISAAC BOT: LuaSocket unavailable: " .. tostring(socket))
end

local function clamp(value)
  return math.max(-1.0, math.min(1.0, tonumber(value) or 0.0))
end

local function hello()
  send(string.format(
    '{"v":%d,"type":"hello","mod":"Isaac Bot Bridge","mod_version":"1.0.0","game_frame":%d,"run_id":%d}',
    PROTOCOL, Game():GetFrameCount(), runId
  ))
end

local function pollCommands()
  if not udp then return end
  while true do
    local packet, ip, port = udp:receivefrom()
    if not packet then break end
    local fields = {}
    for token in string.gmatch(packet, "%S+") do fields[#fields + 1] = token end
    if fields[1] == "V" .. PROTOCOL and fields[2] == "OBSERVE" then
      observers[ip .. ":" .. port] = { ip=ip, port=port, lastFrame=Game():GetFrameCount() }
      hello()
    elseif fields[1] == "V" .. PROTOCOL and fields[2] == "HELLO" then
      peerIp, peerPort = ip, port
      -- A HELLO claims the single local control session. Python processes may
      -- restart and begin their action sequence from one again.
      lastActionSequence = 0
      hello()
    elseif fields[1] == "V" .. PROTOCOL and fields[2] == "ACTION" and #fields >= 12 then
      peerIp, peerPort = ip, port
      local sequence = tonumber(fields[3]) or 0
      if sequence >= lastActionSequence then
        lastActionSequence = sequence
        action.moveX, action.moveY = clamp(fields[4]), clamp(fields[5])
        action.shootX, action.shootY = clamp(fields[6]), clamp(fields[7])
        action.bomb, action.item = fields[8] == "1", fields[9] == "1"
        action.pill, action.card, action.drop = fields[10] == "1", fields[11] == "1", fields[12] == "1"
        lastPacketFrame = Game():GetFrameCount()
      end
    elseif fields[1] == "V" .. PROTOCOL and fields[2] == "COMMAND" then
      peerIp, peerPort = ip, port
      local command = fields[3] or ""
      if command == "AUTO_RESTART" then
        autoRestart = fields[4] == "1"
        sendEvent("auto_restart", ',"enabled":' .. bool(autoRestart))
      elseif command == "RESTART" or command == "NEW_RUN" then
        Isaac.ExecuteCommand("restart")
      elseif command == "PAUSE_AGENT" then
        lastPacketFrame = -10000
      elseif command == "GOAL" then
        currentGoal = { x=tonumber(fields[4]) or 0, y=tonumber(fields[5]) or 0, label=fields[6] or "TARGET" }
      elseif command == "CLEAR_GOAL" then
        currentGoal = nil
      end
    end
  end
end

local function axisValue(button)
  if button == ButtonAction.ACTION_LEFT then return math.max(0, -action.moveX) end
  if button == ButtonAction.ACTION_RIGHT then return math.max(0, action.moveX) end
  if button == ButtonAction.ACTION_UP then return math.max(0, -action.moveY) end
  if button == ButtonAction.ACTION_DOWN then return math.max(0, action.moveY) end
  if button == ButtonAction.ACTION_SHOOTLEFT then return math.max(0, -action.shootX) end
  if button == ButtonAction.ACTION_SHOOTRIGHT then return math.max(0, action.shootX) end
  if button == ButtonAction.ACTION_SHOOTUP then return math.max(0, -action.shootY) end
  if button == ButtonAction.ACTION_SHOOTDOWN then return math.max(0, action.shootY) end
  return nil
end

local function buttonValue(button)
  if button == ButtonAction.ACTION_BOMB then return action.bomb end
  if button == ButtonAction.ACTION_ITEM then return action.item end
  if button == ButtonAction.ACTION_PILLCARD then return action.pill or action.card end
  if button == ButtonAction.ACTION_DROP then return action.drop end
  return nil
end

local function overrideInput(_, entity, hook, button)
  -- Some weapon queries provide no entity even though movement queries provide
  -- the player. Accept nil for gameplay actions; reject explicit non-players.
  if entity and entity.Type ~= EntityType.ENTITY_PLAYER then return nil end
  if Game():GetFrameCount() - lastPacketFrame > WATCHDOG_FRAMES then return nil end
  local axis = axisValue(button)
  if axis ~= nil then
    if hook == InputHook.GET_ACTION_VALUE then return axis end
    return axis > 0.15
  end
  local pressed = buttonValue(button)
  if pressed == nil then return nil end
  if hook == InputHook.GET_ACTION_VALUE then return pressed and 1.0 or 0.0 end
  if hook == InputHook.IS_ACTION_TRIGGERED then
    local wasPressed = previousButtons[button] or false
    previousButtons[button] = pressed
    return pressed and not wasPressed
  end
  return pressed
end

local function entityJson(entity, kind)
  local hp = 0
  local maxHp = 0
  local npc = entity:ToNPC()
  if npc then hp, maxHp = npc.HitPoints, npc.MaxHitPoints end
  local extra = ""
  if kind == "tear" then
    local tear = entity:ToTear()
    if tear then
      -- TearFlags is a BitSet128 userdata in Repentance+. Formatting it with
      -- %d aborts the whole observation while a tear exists. Keep the combat
      -- telemetry numeric and portable; flags can be encoded separately when
      -- the policy starts using individual tear effects.
      extra = string.format(',"damage":%s,"height":%s,"falling_speed":%s,"spawner_type":%s',
        num(tear.CollisionDamage), num(tear.Height), num(tear.FallingSpeed), num(tear.SpawnerType))
    end
  elseif kind == "pickup" then
    local pickup = entity:ToPickup()
    if pickup then
      extra = string.format(',"price":%s,"shop_item":%s', num(pickup.Price), bool(pickup:IsShopItem()))
    end
  end
  return string.format(
    '{"kind":"%s","id":%d,"seed":%d,"entity_type":%d,"variant":%d,"subtype":%d,' ..
    '"x":%s,"y":%s,"vx":%s,"vy":%s,"size":%s,"hp":%s,"max_hp":%s%s}',
    kind, entity.Index, entity.InitSeed, entity.Type, entity.Variant, entity.SubType,
    num(entity.Position.X), num(entity.Position.Y), num(entity.Velocity.X), num(entity.Velocity.Y),
    num(entity.Size), num(hp), num(maxHp), extra
  )
end

local function entitiesJson()
  local result = {}
  for _, entity in ipairs(Isaac.GetRoomEntities()) do
    local kind = nil
    if entity.Type == EntityType.ENTITY_PROJECTILE then kind = "projectile"
    elseif entity.Type == EntityType.ENTITY_TEAR then kind = "tear"
    elseif entity:IsActiveEnemy(false) and not entity:IsDead() then kind = "enemy"
    elseif entity.Type == EntityType.ENTITY_PICKUP then kind = "pickup" end
    if kind then result[#result + 1] = entityJson(entity, kind) end
  end
  return "[" .. table.concat(result, ",") .. "]"
end

local function doorsJson(room)
  local result = {}
  local level = Game():GetLevel()
  for slot = 0, 7 do
    local door = room:GetDoor(slot)
    if door then
      local targetType, visited = 0, 0
      local targetDesc = level:GetRoomByIdx(door.TargetRoomIndex)
      if targetDesc then
        visited = targetDesc.VisitedCount or 0
        if targetDesc.Data then targetType = targetDesc.Data.Type or 0 end
      end
      result[#result + 1] = string.format(
        '{"slot":%d,"target_room":%d,"target_type":%d,"target_visited":%d,"x":%s,"y":%s,"open":%s,"locked":%s}',
        slot, door.TargetRoomIndex, targetType, visited, num(door.Position.X), num(door.Position.Y),
        bool(door:IsOpen()), bool(door:IsLocked())
      )
    end
  end
  return "[" .. table.concat(result, ",") .. "]"
end

local function floorExitsJson(room)
  local result = {}
  for index = 0, room:GetGridSize() - 1 do
    local entity = room:GetGridEntity(index)
    if entity then
      local gridType = entity:GetType()
      if gridType == GridEntityType.GRID_TRAPDOOR or gridType == GridEntityType.GRID_STAIRS then
        local position = room:GetGridPosition(index)
        result[#result + 1] = string.format(
          '{"grid_index":%d,"grid_type":%d,"x":%s,"y":%s}',
          index, gridType, num(position.X), num(position.Y)
        )
      end
    end
  end
  return "[" .. table.concat(result, ",") .. "]"
end

local function gridJson(room)
  local cells = {}
  for index = 0, room:GetGridSize() - 1 do
    cells[#cells + 1] = tostring(room:GetGridCollision(index))
  end
  local origin = room:GetGridPosition(0)
  return string.format(
    '{"width":%d,"height":%d,"size":%d,"cell_size":40,"origin_x":%s,"origin_y":%s,"cells":[%s]}',
    room:GetGridWidth(), room:GetGridHeight(), room:GetGridSize(),
    num(origin.X), num(origin.Y), table.concat(cells, ",")
  )
end

local function goalJson()
  if not currentGoal then return "null" end
  return string.format('{"x":%s,"y":%s,"label":"%s"}', num(currentGoal.x), num(currentGoal.y), esc(currentGoal.label))
end

local function sendObservation()
  if not udp or not peerIp or Game():GetNumPlayers() == 0 then return end
  local game = Game()
  if game:GetFrameCount() % OBSERVATION_INTERVAL ~= 0 then return end
  local player, room, level = Isaac.GetPlayer(0), game:GetRoom(), game:GetLevel()
  local descriptor = level:GetCurrentRoomDesc()
  local payload = string.format(
    '{"v":%d,"type":"observation","frame":%d,"ack":%d,"run_id":%d,"room_visit":%d,' ..
    '"stage":%d,"stage_type":%d,"room_index":%d,"room_type":%d,"room_clear":%s,' ..
    '"player":{"x":%s,"y":%s,"vx":%s,"vy":%s,"hearts":%d,"soul_hearts":%d,' ..
    '"max_hearts":%d,"coins":%d,"keys":%d,"bombs":%d},"goal":%s,"grid":%s,"doors":%s,"floor_exits":%s,"entities":%s}',
    PROTOCOL, game:GetFrameCount(), lastActionSequence, runId, roomVisit,
    level:GetStage(), level:GetStageType(), descriptor.SafeGridIndex, room:GetType(), bool(room:IsClear()),
    num(player.Position.X), num(player.Position.Y), num(player.Velocity.X), num(player.Velocity.Y),
    player:GetHearts(), player:GetSoulHearts(), player:GetMaxHearts(), player:GetNumCoins(),
    player:GetNumKeys(), player:GetNumBombs(), goalJson(), gridJson(room), doorsJson(room), floorExitsJson(room), entitiesJson()
  )
  send(payload)
end

local function update()
  pollCommands()
  local isClear = Game():GetRoom():IsClear()
  if isClear and not roomWasClear then sendEvent("room_clear") end
  roomWasClear = isClear
  sendObservation()
end

-- MC_POST_UPDATE stops on the game-over screen. Keep command polling alive in
-- render callbacks so an interactive Python controller can still request a
-- restart without relying on keyboard fallback.
local function renderPoll()
  pollCommands()
end

local function gameStarted(_, continued)
  runId = runId + 1
  roomVisit = 0
  sendEvent("game_started", ',"continued":' .. bool(continued))
end

local function gameEnded(_, gameOver)
  sendEvent("game_end", ',"game_over":' .. bool(gameOver))
  if gameOver and autoRestart then Isaac.ExecuteCommand("restart") end
end

local function newRoom()
  roomVisit = roomVisit + 1
  roomWasClear = Game():GetRoom():IsClear()
  sendEvent("new_room", ',"room_index":' .. Game():GetLevel():GetCurrentRoomIndex())
end

local function newLevel()
  sendEvent("new_level", ',"stage":' .. Game():GetLevel():GetStage())
end

local function playerDamage(_, entity, amount, flags, source)
  if entity and entity.Type == EntityType.ENTITY_PLAYER then
    local sourceType = source and source.Type or 0
    sendEvent("damage", ',"amount":' .. num(amount) .. ',"flags":' .. flags .. ',"source_type":' .. sourceType)
  end
end

local function npcDeath(_, npc)
  sendEvent("npc_death", ',"entity_type":' .. npc.Type .. ',"variant":' .. npc.Variant)
end

IsaacBot:AddCallback(ModCallbacks.MC_POST_UPDATE, update)
IsaacBot:AddCallback(ModCallbacks.MC_POST_RENDER, renderPoll)
IsaacBot:AddCallback(ModCallbacks.MC_INPUT_ACTION, overrideInput)
IsaacBot:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, gameStarted)
IsaacBot:AddCallback(ModCallbacks.MC_POST_GAME_END, gameEnded)
IsaacBot:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, newRoom)
IsaacBot:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, newLevel)
IsaacBot:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, playerDamage)
IsaacBot:AddCallback(ModCallbacks.MC_POST_NPC_DEATH, npcDeath)
