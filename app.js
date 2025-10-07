const express = require('express');
const http = require('http');
const cors = require('cors');
const { Server } = require('socket.io');
const bcryptjs = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { MongoClient, ObjectId } = require('mongodb');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(express.json());
const server = http.createServer(app);

// MongoDB连接配置
const mongoConfig = {
  url: process.env.MONGO_URL || 'mongodb://localhost:27017',
  dbName: process.env.DB_NAME || 'chat_app'
};

// 用户存储
let users = {};

// Socket.io服务器
const io = new Server(server, {
  cors: {
    origin: "*",
  }
});

// JWT密钥
const JWT_SECRET = 'your_jwt_secret';

// MongoDB连接
let client;
let db;

// 初始化MongoDB连接
async function initDb() {
  try {
    client = new MongoClient(mongoConfig.url);
    await client.connect();
    db = client.db(mongoConfig.dbName);
    
    console.log('MongoDB连接成功');
    
    // 创建索引
    await createIndexes();
    console.log('数据库索引创建完成');
  } catch (error) {
    console.error('MongoDB连接失败:', error);
  }
}

// 创建必要的索引
async function createIndexes() {
  try {
    // 用户集合索引
    await db.collection('users').createIndex({ username: 1 }, { unique: true });
    
    // 好友请求索引
    await db.collection('friend_requests').createIndex({ sender_id: 1, receiver_id: 1 });
    
    // 好友关系索引
    await db.collection('friendships').createIndex({ user_id: 1, friend_id: 1 });
    
    // 群组消息索引
    await db.collection('group_messages').createIndex({ group_id: 1, created_at: -1 });
    
    // 私聊消息索引
    await db.collection('private_messages').createIndex({ 
      sender_id: 1, receiver_id: 1, created_at: -1 
    });
    
    // 群组成员索引
    await db.collection('group_members').createIndex({ group_id: 1, user_id: 1 });
    
    console.log('索引创建完成');
  } catch (error) {
    console.log('索引创建警告:', error.message);
  }
}

// 用户认证中间件
const authMiddleware = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ message: '未提供认证令牌' });
  }
  
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ message: '无效的认证令牌' });
  }
};

// 注册API
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ message: '用户名和密码不能为空' });
  }
  
  try {
    // 检查用户是否已存在
    const existingUser = await db.collection('users').findOne({ username });
    
    if (existingUser) {
      return res.status(400).json({ message: '用户名已存在' });
    }
    
    // 加密密码
    const hashedPassword = await bcryptjs.hash(password, 10);
    
    // 创建新用户
    const result = await db.collection('users').insertOne({
      username,
      password: hashedPassword,
      created_at: new Date(),
      updated_at: new Date()
    });
    
    res.status(201).json({ 
      message: '注册成功',
      userId: result.insertedId
    });
  } catch (error) {
    console.error('注册失败:', error);
    if (error.code === 11000) {
      return res.status(400).json({ message: '用户名已存在' });
    }
    res.status(500).json({ message: '服务器错误' });
  }
});

// 登录API
app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ message: '用户名和密码不能为空' });
  }
  
  try {
    // 查询用户
    const user = await db.collection('users').findOne({ username });
    
    if (!user) {
      return res.status(401).json({ message: '用户名或密码错误' });
    }
    
    // 验证密码
    const isPasswordValid = await bcryptjs.compare(password, user.password);
    
    if (!isPasswordValid) {
      return res.status(401).json({ message: '用户名或密码错误' });
    }
    
    // 生成JWT令牌
    const token = jwt.sign(
      { id: user._id.toString(), username: user.username },
      JWT_SECRET,
      { expiresIn: '12h' }
    );
    
    // 记录IP地址
    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
    await db.collection('ip_records').insertOne({
      user_id: user._id,
      ip_address: ip,
      created_at: new Date()
    });
    
    res.json({ 
      token, 
      user: { 
        id: user._id.toString(), 
        username: user.username 
      } 
    });
  } catch (error) {
    console.error('登录失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取用户列表API
app.get('/api/users', authMiddleware, async (req, res) => {
  try {
    const users = await db.collection('users')
      .find({}, { projection: { password: 0 } })
      .toArray();
    
    const userList = users.map(user => ({
      id: user._id.toString(),
      username: user.username
    }));
    
    res.json({ users: userList });
  } catch (error) {
    console.error('获取用户列表失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 搜索用户API
app.get('/api/users/search', authMiddleware, async (req, res) => {
  const { username } = req.query;
  
  if (!username) {
    return res.status(400).json({ message: '请提供用户名进行搜索' });
  }
  
  try {
    const users = await db.collection('users').find({
      username: { $regex: username, $options: 'i' },
      _id: { $ne: new ObjectId(req.user.id) }
    }, { projection: { password: 0 } }).toArray();
    
    const userList = users.map(user => ({
      id: user._id.toString(),
      username: user.username
    }));
    
    console.log('搜索用户结果:', userList);
    
    res.json({ users: userList });
  } catch (error) {
    console.error('搜索用户失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 发送好友请求API
app.post('/api/friend-requests', authMiddleware, async (req, res) => {
  const { receiverId } = req.body;
  const senderId = req.user.id;
  
  if (!receiverId) {
    return res.status(400).json({ message: '接收者ID不能为空' });
  }
  
  try {
    console.log('发送好友请求:', { senderId, receiverId });
    
    // 检查用户是否存在
    const user = await db.collection('users').findOne({ 
      _id: new ObjectId(receiverId) 
    });
    
    if (!user) {
      return res.status(404).json({ message: '用户不存在' });
    }
    
    // 检查是否已经是好友
    const friendship = await db.collection('friendships').findOne({
      $or: [
        { user_id: new ObjectId(senderId), friend_id: new ObjectId(receiverId) },
        { user_id: new ObjectId(receiverId), friend_id: new ObjectId(senderId) }
      ]
    });
    
    if (friendship) {
      return res.status(400).json({ message: '你们已经是好友了' });
    }
    
    // 检查是否已经发送过请求
    const existingRequest = await db.collection('friend_requests').findOne({
      sender_id: new ObjectId(senderId),
      receiver_id: new ObjectId(receiverId)
    });
    
    if (existingRequest) {
      if (existingRequest.status === 'pending') {
        return res.status(400).json({ message: '你已经发送过好友请求，等待对方接受' });
      } else if (existingRequest.status === 'rejected') {
        // 如果之前的请求被拒绝，允许重新发送
        await db.collection('friend_requests').updateOne(
          { _id: existingRequest._id },
          { 
            $set: { 
              status: 'pending', 
              updated_at: new Date() 
            } 
          }
        );
        
        return res.status(200).json({ message: '好友请求已重新发送' });
      }
    }
    
    // 检查对方是否已经向你发送请求
    const reverseRequest = await db.collection('friend_requests').findOne({
      sender_id: new ObjectId(receiverId),
      receiver_id: new ObjectId(senderId),
      status: 'pending'
    });
    
    if (reverseRequest) {
      return res.status(400).json({ message: '对方已经向你发送了好友请求，请查看你的好友请求列表' });
    }
    
    // 发送好友请求
    await db.collection('friend_requests').insertOne({
      sender_id: new ObjectId(senderId),
      receiver_id: new ObjectId(receiverId),
      status: 'pending',
      created_at: new Date(),
      updated_at: new Date()
    });
    
    res.status(201).json({ message: '好友请求已发送' });
  } catch (error) {
    console.error('发送好友请求失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取好友请求API
app.get('/api/friend-requests', authMiddleware, async (req, res) => {
  const userId = req.user.id;
  
  try {
    // 获取收到的好友请求
    const receivedRequests = await db.collection('friend_requests').aggregate([
      {
        $match: {
          receiver_id: new ObjectId(userId),
          status: 'pending'
        }
      },
      {
        $lookup: {
          from: 'users',
          localField: 'sender_id',
          foreignField: '_id',
          as: 'sender'
        }
      },
      {
        $unwind: '$sender'
      },
      {
        $project: {
          id: '$_id',
          sender_id: 1,
          sender_username: '$sender.username',
          status: 1,
          created_at: 1,
          updated_at: 1
        }
      },
      { $sort: { created_at: -1 } }
    ]).toArray();
    
    // 获取发送的好友请求
    const sentRequests = await db.collection('friend_requests').aggregate([
      {
        $match: {
          sender_id: new ObjectId(userId)
        }
      },
      {
        $lookup: {
          from: 'users',
          localField: 'receiver_id',
          foreignField: '_id',
          as: 'receiver'
        }
      },
      {
        $unwind: '$receiver'
      },
      {
        $project: {
          id: '$_id',
          receiver_id: 1,
          receiver_username: '$receiver.username',
          status: 1,
          created_at: 1,
          updated_at: 1
        }
      },
      { $sort: { created_at: -1 } }
    ]).toArray();
    
    console.log('获取好友请求:', { received: receivedRequests, sent: sentRequests });
    
    res.json({
      received: receivedRequests,
      sent: sentRequests
    });
  } catch (error) {
    console.error('获取好友请求失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 处理好友请求API
app.put('/api/friend-requests/:requestId', authMiddleware, async (req, res) => {
  const { requestId } = req.params;
  const { status } = req.body;
  const userId = req.user.id;
  
  if (!status || !['accepted', 'rejected'].includes(status)) {
    return res.status(400).json({ message: '状态无效，必须是 accepted 或 rejected' });
  }
  
  try {
    console.log('处理好友请求:', { requestId, status });
    
    // 检查请求是否存在且接收者是当前用户
    const request = await db.collection('friend_requests').findOne({
      _id: new ObjectId(requestId),
      receiver_id: new ObjectId(userId),
      status: 'pending'
    });
    
    if (!request) {
      return res.status(404).json({ message: '好友请求不存在或已处理' });
    }
    
    // 更新请求状态
    await db.collection('friend_requests').updateOne(
      { _id: new ObjectId(requestId) },
      { 
        $set: { 
          status, 
          updated_at: new Date() 
        } 
      }
    );
    
    // 如果接受请求，添加好友关系
    if (status === 'accepted') {
      // 检查是否已经是好友
      const existingFriendship = await db.collection('friendships').findOne({
        $or: [
          { user_id: new ObjectId(userId), friend_id: request.sender_id },
          { user_id: request.sender_id, friend_id: new ObjectId(userId) }
        ]
      });
      
      if (!existingFriendship) {
        // 添加双向好友关系
        await db.collection('friendships').insertMany([
          {
            user_id: new ObjectId(userId),
            friend_id: request.sender_id,
            created_at: new Date()
          },
          {
            user_id: request.sender_id,
            friend_id: new ObjectId(userId),
            created_at: new Date()
          }
        ]);
      }
      
      res.json({ message: '已接受好友请求' });
    } else {
      res.json({ message: '已拒绝好友请求' });
    }
  } catch (error) {
    console.error('处理好友请求失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取好友列表API
app.get('/api/friends', authMiddleware, async (req, res) => {
  const userId = req.user.id;
  
  try {
    const friends = await db.collection('friendships').aggregate([
      {
        $match: {
          user_id: new ObjectId(userId)
        }
      },
      {
        $lookup: {
          from: 'users',
          localField: 'friend_id',
          foreignField: '_id',
          as: 'friend'
        }
      },
      {
        $unwind: '$friend'
      },
      {
        $project: {
          id: '$friend._id',
          username: '$friend.username'
        }
      },
      { $sort: { username: 1 } }
    ]).toArray();
    
    console.log('获取好友列表:', friends);
    
    res.json({ friends });
  } catch (error) {
    console.error('获取好友列表失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 删除好友API
app.delete('/api/friends/:friendId', authMiddleware, async (req, res) => {
  const { friendId } = req.params;
  const userId = req.user.id;
  
  try {
    console.log('删除好友:', { userId, friendId });
    
    // 检查是否是好友
    const friendship = await db.collection('friendships').findOne({
      user_id: new ObjectId(userId),
      friend_id: new ObjectId(friendId)
    });
    
    if (!friendship) {
      return res.status(404).json({ message: '好友关系不存在' });
    }
    
    // 删除双向好友关系
    await db.collection('friendships').deleteMany({
      $or: [
        { user_id: new ObjectId(userId), friend_id: new ObjectId(friendId) },
        { user_id: new ObjectId(friendId), friend_id: new ObjectId(userId) }
      ]
    });
    
    res.json({ message: '好友已删除' });
  } catch (error) {
    console.error('删除好友失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 创建群组API
app.post('/api/groups/create', authMiddleware, async (req, res) => {
  const { name, description } = req.body;
  const creatorId = req.user.id;
  
  if (!name) {
    return res.status(400).json({ message: '群组名称不能为空' });
  }
  
  try {
    console.log('创建群组:', { creatorId, name, description });
    
    // 创建群组
    const groupResult = await db.collection('groups').insertOne({
      name,
      description: description || '',
      creator_id: new ObjectId(creatorId),
      created_at: new Date(),
      updated_at: new Date()
    });
    
    const groupId = groupResult.insertedId;
    
    // 添加创建者为群成员（管理员角色）
    await db.collection('group_members').insertOne({
      group_id: groupId,
      user_id: new ObjectId(creatorId),
      role: 'admin',
      joined_at: new Date()
    });
    
    res.status(201).json({ 
      message: '群组创建成功',
      group: {
        id: groupId.toString(),
        name,
        description: description || '',
        creator_id: creatorId
      }
    });
  } catch (error) {
    console.error('创建群组失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取我的群聊列表
app.get('/api/groups/my', authMiddleware, async (req, res) => {
  const userId = req.user.id;
  
  try {
    const groups = await db.collection('group_members').aggregate([
      {
        $match: {
          user_id: new ObjectId(userId)
        }
      },
      {
        $lookup: {
          from: 'groups',
          localField: 'group_id',
          foreignField: '_id',
          as: 'group'
        }
      },
      {
        $unwind: '$group'
      },
      {
        $lookup: {
          from: 'group_members',
          localField: 'group_id',
          foreignField: 'group_id',
          as: 'members'
        }
      },
      {
        $project: {
          id: '$group._id',
          name: '$group.name',
          description: '$group.description',
          creator_id: '$group.creator_id',
          created_at: '$group.created_at',
          updated_at: '$group.updated_at',
          role: '$role',
          member_count: { $size: '$members' }
        }
      },
      { $sort: { updated_at: -1 } }
    ]).toArray();
    
    console.log('获取我的群聊列表:', groups);
    
    res.json({ groups });
  } catch (error) {
    console.error('获取群组列表失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取群聊详情
app.get('/api/groups/:groupId', authMiddleware, async (req, res) => {
  const { groupId } = req.params;
  const userId = req.user.id;
  
  try {
    // 检查群组是否存在
    const group = await db.collection('groups').findOne({
      _id: new ObjectId(groupId)
    });
    
    if (!group) {
      return res.status(404).json({ message: '群组不存在' });
    }
    
    // 检查用户是否是群成员
    const membership = await db.collection('group_members').findOne({
      group_id: new ObjectId(groupId),
      user_id: new ObjectId(userId)
    });
    
    if (!membership) {
      return res.status(403).json({ message: '你不是该群成员' });
    }
    
    // 获取群成员列表
    const members = await db.collection('group_members').aggregate([
      {
        $match: {
          group_id: new ObjectId(groupId)
        }
      },
      {
        $lookup: {
          from: 'users',
          localField: 'user_id',
          foreignField: '_id',
          as: 'user'
        }
      },
      {
        $unwind: '$user'
      },
      {
        $project: {
          user_id: 1,
          username: '$user.username',
          role: 1,
          joined_at: 1
        }
      },
      {
        $sort: {
          role: 1, // admin 优先
          joined_at: 1
        }
      }
    ]).toArray();
    
    // 获取成员数量
    const memberCount = await db.collection('group_members').countDocuments({
      group_id: new ObjectId(groupId)
    });
    
    const groupInfo = {
      id: group._id.toString(),
      name: group.name,
      description: group.description,
      creator_id: group.creator_id.toString(),
      created_at: group.created_at,
      updated_at: group.updated_at,
      member_count: memberCount
    };
    
    console.log('获取群聊详情:', { group: groupInfo, members });
    
    res.json({
      group: groupInfo,
      members,
      userRole: membership.role
    });
  } catch (error) {
    console.error('获取群组详情失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 邀请好友加入群聊
app.post('/api/groups/:groupId/invite', authMiddleware, async (req, res) => {
  const { groupId } = req.params;
  const { friendIds } = req.body;
  const userId = req.user.id;
  
  if (!friendIds || !Array.isArray(friendIds) || friendIds.length === 0) {
    return res.status(400).json({ message: '好友ID列表不能为空' });
  }
  
  try {
    console.log('邀请好友加入群聊:', { groupId, userId, friendIds });
    
    // 检查群组是否存在
    const group = await db.collection('groups').findOne({
      _id: new ObjectId(groupId)
    });
    
    if (!group) {
      return res.status(404).json({ message: '群组不存在' });
    }
    
    // 检查用户是否是群成员
    const membership = await db.collection('group_members').findOne({
      group_id: new ObjectId(groupId),
      user_id: new ObjectId(userId)
    });
    
    if (!membership) {
      return res.status(403).json({ message: '你不是该群成员，无法邀请好友' });
    }
    
    const addedFriends = [];
    const errors = [];
    
    for (const friendId of friendIds) {
      try {
        // 检查是否是好友
        const friendship = await db.collection('friendships').findOne({
          user_id: new ObjectId(userId),
          friend_id: new ObjectId(friendId)
        });
        
        if (!friendship) {
          errors.push(`ID为${friendId}的用户不是你的好友`);
          continue;
        }
        
        // 检查是否已经是群成员
        const existingMember = await db.collection('group_members').findOne({
          group_id: new ObjectId(groupId),
          user_id: new ObjectId(friendId)
        });
        
        if (existingMember) {
          errors.push(`ID为${friendId}的用户已经是群成员`);
          continue;
        }
        
        // 添加为群成员
        await db.collection('group_members').insertOne({
          group_id: new ObjectId(groupId),
          user_id: new ObjectId(friendId),
          role: 'member',
          joined_at: new Date()
        });
        
        addedFriends.push(friendId);
      } catch (err) {
        errors.push(`处理用户${friendId}时出错: ${err.message}`);
      }
    }
    
    res.status(200).json({
      message: `已成功邀请${addedFriends.length}位好友加入群聊`,
      addedFriends,
      errors: errors.length > 0 ? errors : undefined
    });
  } catch (error) {
    console.error('邀请好友加入群聊失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 群聊消息相关API
app.get('/api/groups/:groupId/messages', authMiddleware, async (req, res) => {
  const { groupId } = req.params;
  const userId = req.user.id;
  const { limit = 50, before } = req.query;
  
  try {
    // 检查用户是否是群成员
    const membership = await db.collection('group_members').findOne({
      group_id: new ObjectId(groupId),
      user_id: new ObjectId(userId)
    });
    
    if (!membership) {
      return res.status(403).json({ message: '你不是该群成员，无法查看消息' });
    }
    
    // 构建查询条件
    let query = { group_id: new ObjectId(groupId) };
    
    if (before) {
      query._id = { $lt: new ObjectId(before) };
    }
    
    // 获取消息
    const messages = await db.collection('group_messages').aggregate([
      { $match: query },
      {
        $lookup: {
          from: 'users',
          localField: 'sender_id',
          foreignField: '_id',
          as: 'sender'
        }
      },
      {
        $unwind: '$sender'
      },
      {
        $project: {
          id: '$_id',
          sender_id: 1,
          sender_name: '$sender.username',
          content: 1,
          message_type: { $ifNull: ['$message_type', 'text'] },
          created_at: 1
        }
      },
      { $sort: { _id: -1 } },
      { $limit: parseInt(limit) }
    ]).toArray();
    
    console.log('获取群聊消息:', { groupId, userId, messageCount: messages.length });
    
    res.json({ messages: messages.reverse() });
  } catch (error) {
    console.error('获取群聊消息失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 发送群聊消息
app.post('/api/groups/:groupId/messages', authMiddleware, async (req, res) => {
  const { groupId } = req.params;
  const { content, messageType = 'text' } = req.body;
  const senderId = req.user.id;
  
  if (!content) {
    return res.status(400).json({ message: '消息内容不能为空' });
  }
  
  try {
    console.log('发送群聊消息:', { groupId, senderId, messageType });
    
    // 检查用户是否是群成员
    const membership = await db.collection('group_members').findOne({
      group_id: new ObjectId(groupId),
      user_id: new ObjectId(senderId)
    });
    
    if (!membership) {
      return res.status(403).json({ message: '你不是该群成员，无法发送消息' });
    }
    
    // 发送消息
    const messageResult = await db.collection('group_messages').insertOne({
      group_id: new ObjectId(groupId),
      sender_id: new ObjectId(senderId),
      content,
      message_type: messageType,
      created_at: new Date()
    });
    
    // 更新群组最后活动时间
    await db.collection('groups').updateOne(
      { _id: new ObjectId(groupId) },
      { $set: { updated_at: new Date() } }
    );
    
    // 获取发送者信息用于Socket.io广播
    const user = await db.collection('users').findOne({ 
      _id: new ObjectId(senderId) 
    });
    
    const message = {
      id: messageResult.insertedId.toString(),
      group_id: groupId,
      sender_id: senderId,
      sender_name: user.username,
      content,
      message_type: messageType,
      created_at: new Date()
    };
    
    // 通过Socket.io广播消息
    io.emit('group_message', message);
    
    res.status(201).json({
      message: '消息已发送',
      messageId: messageResult.insertedId.toString()
    });
  } catch (error) {
    console.error('发送群聊消息失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// Socket.io连接处理
io.on('connection', (socket) => {
  console.log('用户连接', socket.id);

  // 登录
  socket.on('login', ({ username }) => {
    users[socket.id] = username;
    io.emit('userList', Object.values(users));
    socket.emit('loginSuccess', username);
  });

  // 发送消息
  socket.on('message', async (msg) => {
    const from = users[socket.id];
    if(!from) return; //未登录不允许发消息

    const message = { 
      user: from, 
      text: msg, 
      time: new Date().toISOString()
    };
    
    io.emit('message', message);
    
    // 将消息保存到数据库
    try {
      // 默认保存到ID为1的群组（可以根据需要调整）
      await db.collection('group_messages').insertOne({
        group_id: new ObjectId('507f1f77bcf86cd799439011'), // 默认群组ID
        sender_id: new ObjectId('507f1f77bcf86cd799439012'), // 默认用户ID
        content: msg,
        message_type: 'text',
        created_at: new Date()
      });
    } catch (error) {
      console.error('保存消息失败:', error);
    }
  });

  socket.on('disconnect', () => {
    delete users[socket.id];
    io.emit('userList', Object.values(users));
    console.log('用户断开', socket.id);
  });
});

// 文件上传配置
const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, uploadDir);
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    const ext = path.extname(file.originalname);
    cb(null, 'file-' + uniqueSuffix + ext);
  }
});

const fileFilter = (req, file, cb) => {
  // 允许所有文件类型，但限制大小
  cb(null, true);
};

const upload = multer({ 
  storage: storage,
  fileFilter: fileFilter,
  limits: {
    fileSize: 10 * 1024 * 1024 // 限制10MB
  }
});

// 文件上传API
app.post('/api/upload/file', authMiddleware, upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: '没有上传文件' });
    }
    
    const filePath = `/uploads/${req.file.filename}`;
    
    res.status(201).json({ 
      message: '文件上传成功',
      filePath: filePath,
      fileName: req.file.originalname
    });
  } catch (error) {
    console.error('文件上传失败:', error);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 静态文件服务
app.use('/uploads', express.static(uploadDir));

// 健康检查API
app.get('/health', (req, res) => res.send('IM服务正常运行 - MongoDB版本'));

// 启动服务器
const PORT = process.env.PORT || 3001;
server.listen(PORT, '0.0.0.0', async () => {
  console.log(`后端服务监听端口 ${PORT} - 使用MongoDB`);
  await initDb();
});

// 优雅关闭
process.on('SIGINT', async () => {
  console.log('正在关闭服务器...');
  if (client) {
    await client.close();
    console.log('MongoDB连接已关闭');
  }
  process.exit(0);
});