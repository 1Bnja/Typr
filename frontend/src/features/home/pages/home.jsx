import { homeContent } from "../content"
import landingKeyboard from '../assets/landing-keyboard.png'
import Button from '../../../components/button'
const Home = () => {
  return (
    <section className="flex flex-1 flex-col items-center justify-center p-8 pb-0">
      <div className="flex flex-1 flex-col items-center justify-center">
      <h1 className="text-7xl font-extrabold whitespace-pre-line text-center mb-12 max-w-s">{homeContent.title}</h1>
      <p className="text-center mb-12 max-w-md">{homeContent.description}</p>
      <div className="flex flex-row gap-3">
        <Button variant="primary" size="lg">Start test</Button>
        <Button variant="secondary" size="lg">View lessons</Button>
      </div>
      <div className="flex flex-row gap-3 mt-12 text-center text-gray-500 gap-x-12">
        <p>92 ppm average</p>
        <p>+31% in 30 days</p>
        <p>Free for everyone</p>
      </div>
      </div>
        <img
        src={landingKeyboard}
        alt="Home image"
        className='w-full max-w-7xl object-contain object-bottom mt-auto mx-auto'
        />
    </section>
  )
}

export default Home
