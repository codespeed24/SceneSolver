// scenesolver-backend/server.js

const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors'); // --- IMPORT CORS ---
const dotenv = require('dotenv');
const authRoutes = require('./routes/auth');
const analysisRoutes = require('./routes/analysis');

dotenv.config();

const app = express();

// --- SETUP CORS MIDDLEWARE ---
// Allow all origins for robust local development (supports localhost, 127.0.0.1, and local IP)
app.use(cors());

app.use(express.json());

app.use(express.static('public'));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/analysis', analysisRoutes);

// Connect to MongoDB
mongoose.connect(process.env.MONGO_URI, {
  useNewUrlParser: true,
  useUnifiedTopology: true
})
.then(() => {
  console.log('✅ MongoDB connected');
  // --- UPDATE: The port is now defined in a variable for clarity ---
  const PORT = process.env.PORT || 5000;
  app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));
})
.catch(err => console.error('❌ MongoDB connection error:', err));