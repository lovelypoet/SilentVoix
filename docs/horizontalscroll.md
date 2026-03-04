body {
  margin: 0;
  padding: 0;
	background-image: linear-gradient(to right, white , #ffedb5);
}

.container::-webkit-scrollbar {
  display: none;
}

.outterContainer {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.container {
  width: 400px;
  height: 700px;
  overflow-y: auto;
  overflow-x: hidden;
  transform: rotate(-90deg) translateY(-100px);
  display: flex;
  flex-direction: column;
  gap: 160px;
  padding: 100px 0;
}

img {
  width: 400px;
  transform: rotate(90deg);
  object-fit: cover;
  border-radius: 10px;
}

@media (max-width: 600px){
	.container{
		height: 350px;
		padding: 120px 0;
	}
}

<div class="outterContainer">
  <div class="container">
  </div>
</div>

<!-- NOTE : JS is only used to display/add images -->

